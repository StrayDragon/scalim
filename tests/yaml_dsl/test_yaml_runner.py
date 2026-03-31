import csv
from pathlib import Path

import pytest

from scalim.dsl.by_yaml import (
    BookResourceOverride,
    FileResourceOverride,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    RunOverrides,
    RunResult,
    run,
)
from scalim.dsl.by_yaml.runtime.observability import (
    _create_performance_observer_from_config,
    _create_relation_observer_from_config,
    compile_observability_spec,
)
from scalim.execution.run_ir import ExecutionResult, export_layout_from_demand_ir
from scalim.planning import PlanBuilder
from scalim.dsl.by_yaml.schema_dsl.models import (
    DemandConfig,
    LoggingConfig,
    ObservabilityConfig,
    PerformanceConfig,
    PerformanceReportConfig,
    PerformanceThresholdsConfig,
    RelationReportConfig,
    RelationsConfig,
    RowGapConfig,
    TraceConfig,
    MemoryOptimizationConfig,
)
from scalim.events import EVENT_PIPELINE_START
from scalim.events._events import BatchEndEvent, BatchStartEvent, LoaderCallEvent, PipelineEndEvent, PipelineStartEvent
from scalim.hooks import BaseHook
from scalim.ob.observer import Observer
from scalim.ob.presets.logs import LoggingObserver, PrettyLoggingObserver
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim.ob.presets.row_gap import RowGapObserver
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.sinks import InMemoryRowSink
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr
from tests.support.pathing import fixtures_dir
from tests.support.testing_utils import missing_optional_dependency

_ALLOWED_MODULES = frozenset(["scalim_misc.example_report_ir"])


def _demo_yaml_path() -> Path:
    return fixtures_dir() / "order_report.yaml"


def _write_yaml_without_output(tmp_path: Path, source_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    output_path = tmp_path / "order_report_no_output.yaml"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _write_yaml_with_column_output(tmp_path: Path, source_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    output_path = tmp_path / "order_report_column.yaml"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _write_yaml_with_output_path(tmp_path: Path, source_path: Path, output_path: Path) -> Path:
    from scalim.vendor.yamlx import yaml

    config = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise TypeError("expected mapping")
    config["resources"] = {"files": {"detail_csv": {"kind": "csv_file", "path": str(output_path)}}}
    config["outputs"] = [
        {
            "name": "detail",
            "to": {"file": "detail_csv"},
            "fields": ["order_id"],
        }
    ]

    yaml_path = tmp_path / "order_report_custom_output.yaml"
    yaml_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return yaml_path


def _write_yaml_with_named_headers(tmp_path: Path, source_path: Path, output_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    yaml_path = tmp_path / "order_report_named_headers.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def _build_default_yaml(_tmp_path: Path) -> Path:
    return _demo_yaml_path()


def _build_column_yaml(tmp_path: Path) -> Path:
    return _write_yaml_with_column_output(tmp_path, _demo_yaml_path())


class _CaptureHook(BaseHook):
    def __init__(self) -> None:
        self.pipeline_started = False

    def on_pipeline_start(self, event) -> None:  # type: ignore[override]
        self.pipeline_started = True


@pytest.mark.parametrize(
    "yaml_builder,output_name,sink_factory,check_header",
    [
        (
            _build_default_yaml,
            "order_report.csv",
            InMemoryRowSink,
            True,
        ),
    ],
    ids=["default-streaming"],
)
def test_run_outputs_and_returns_data(
    example_model,
    tmp_path: Path,
    yaml_builder,
    output_name: str,
    sink_factory,
    check_header: bool,
) -> None:
    yaml_path = yaml_builder(tmp_path)
    output_path = tmp_path / "nested" / output_name

    sink = sink_factory() if sink_factory is not None else None
    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(
            outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),),
            resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(output_path))}),
        ),
        sink=sink,
    )

    assert result.total_rows > 0
    assert output_path.exists()
    assert result.output_path == str(output_path)
    if sink is not None:
        assert sink.get_data()

    if check_header:
        header = output_path.read_text(encoding="utf-8").splitlines()[0]
        assert "订单ID" in header


def test_run_header_fields_output_by_name_uses_field_names(example_model, tmp_path: Path) -> None:
    output_path = tmp_path / "order_report_named.csv"
    yaml_path = _write_yaml_with_named_headers(tmp_path, _demo_yaml_path(), output_path)

    fields = ["order_id"]
    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(
            outputs=(
                OutputOverride(
                    name="detail",
                    fields=tuple(fields),
                    to=OutputToOverride(file="detail_csv"),
                    write=OutputWriteOverride(header_fields_output_by="name"),
                ),
            ),
            resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(output_path))}),
        ),
    )

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        first_row = next(reader)

    export_layout = export_layout_from_demand_ir(result.demand_ir, fields, header_fields_output_by="name")
    expected_headers = list(export_layout.header_names or export_layout.field_ids)
    assert header == expected_headers
    assert first_row[0] != ""


@pytest.mark.parametrize(
    ("write_override", "expected_header"),
    [
        (None, ["订单ID", "金额"]),
        (OutputWriteOverride(header_fields_output_by="field_id"), ["order_id", "amount"]),
    ],
    ids=["books-default-name", "books-explicit-field-id"],
)
def test_run_books_output_header_fields_output_by_controls_actual_xlsx_header(
    example_model,
    tmp_path: Path,
    write_override,
    expected_header,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    output_path = tmp_path / "order_report_books.xlsx"

    _ = run(
        str(_demo_yaml_path()),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(
            outputs=(
                OutputOverride(
                    name="detail",
                    fields=("order_id", "amount"),
                    to=OutputToOverride(book="report", sheet="明细"),
                    write=write_override,
                ),
            ),
            resources=ResourcesOverride(books={"report": BookResourceOverride(kind="xlsx_file", path=str(output_path))}),
        ),
    )

    wb = openpyxl.load_workbook(str(output_path))
    ws = wb["明细"]
    header = [cell for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    assert header == expected_header


def test_run_in_memory_sink_without_output_path_returns_data(example_model, tmp_path: Path) -> None:
    yaml_path = _write_yaml_without_output(tmp_path, _demo_yaml_path())
    sink = InMemoryRowSink()

    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        sink=sink,
    )

    assert result.output_path is None
    assert sink.get_data()
    assert "order_id" in sink.get_data()[0]


def test_run_column_sink_and_custom_hooks(example_model, tmp_path: Path) -> None:
    yaml_path = _write_yaml_with_column_output(tmp_path, _demo_yaml_path())
    output_path = tmp_path / "order_report_column.csv"
    hook = _CaptureHook()

    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(
            outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),),
            resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(output_path))}),
        ),
        components=[hook],
    )

    assert hook.pipeline_started is True
    assert result.output_path == str(output_path)
    assert output_path.exists()


def test_run_registers_observer_components(example_model, tmp_path: Path) -> None:
    yaml_path = _demo_yaml_path()
    output_path = tmp_path / "order_report_component_observer.csv"

    class _CaptureObserver(Observer):
        event_types = {EVENT_PIPELINE_START}

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event) -> None:  # type: ignore[override]
            self.events.append(event)

    observer = _CaptureObserver()
    _ = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        components=[observer],
        overrides=RunOverrides(
            outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),),
            resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(output_path))}),
        ),
    )

    assert observer.events
    assert observer.events[0].event_type == EVENT_PIPELINE_START


def test_run_raises_typeerror_on_invalid_component(example_model, tmp_path: Path) -> None:
    yaml_path = _write_yaml_without_output(tmp_path, _demo_yaml_path())
    with pytest.raises(TypeError, match=r"Invalid component at index 0"):
        _ = run(
            str(yaml_path),
            allowed_modules=_ALLOWED_MODULES,
            components=[object()],  # type: ignore[list-item]
        )


def test_run_uses_config_output_path(example_model, tmp_path: Path) -> None:
    yaml_path = _write_yaml_with_output_path(tmp_path, _demo_yaml_path(), tmp_path / "order_report_custom.csv")

    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
    )

    assert result.output_path == str(tmp_path / "order_report_custom.csv")
    assert Path(result.output_path).exists()


def test_pretty_logging_observer_renders_stats(capsys) -> None:
    observer = PrettyLoggingObserver()

    observer.on_pipeline_start(PipelineStartEvent(targets=["a", "b"], batch_size=2))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2]))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.01))
    observer.on_loader_call(LoaderCallEvent(loader_name="demo_loader", params={}, result={1: {"x": 1}}, duration=0.5))
    observer.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.02))

    output = capsys.readouterr().out
    assert "[scalim] pretty:" in output
    assert "pipeline_start" in output
    assert "pipeline_end" in output
    assert "loader=demo_loader" in output


def test_pretty_logging_observer_renders_batch_duration_from_event(capsys) -> None:
    observer = PrettyLoggingObserver()

    observer.on_pipeline_start(PipelineStartEvent(targets=["a"], batch_size=1))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=1.23))

    output = capsys.readouterr().out
    assert "duration_s=1.23" in output


def test_pretty_logging_observer_reuses_user_stdout_handler_by_name() -> None:
    import logging
    import sys

    import scalim.ob.presets.logs as logs_mod

    logger = logs_mod._PRETTY_LOGGER
    orig_handlers = list(logger.handlers)
    orig_level = int(logger.level)
    orig_propagate = bool(logger.propagate)
    orig_slot_handler = logs_mod._pretty_stdout_handler_slot.handler
    orig_slot_owned = bool(logs_mod._pretty_stdout_handler_slot.owned)

    try:
        logger.handlers[:] = []
        logs_mod._pretty_stdout_handler_slot.handler = None
        logs_mod._pretty_stdout_handler_slot.owned = False

        other_handler = logging.StreamHandler(stream=sys.stdout)
        other_handler.name = "other"
        logger.addHandler(other_handler)

        user_handler = logging.StreamHandler(stream=sys.stdout)
        user_handler.name = logs_mod._PRETTY_STDOUT_HANDLER_NAME
        logger.addHandler(user_handler)

        _ = PrettyLoggingObserver()

        assert logger.handlers == [other_handler, user_handler]
        assert logs_mod._pretty_stdout_handler_slot.handler is user_handler
        assert not logs_mod._pretty_stdout_handler_slot.owned

        logger.handlers[:] = []
        logs_mod._pretty_stdout_handler_slot.handler = None
        logs_mod._pretty_stdout_handler_slot.owned = False

        _ = PrettyLoggingObserver()
        owned_handler = logs_mod._pretty_stdout_handler_slot.handler
        assert owned_handler is not None
        assert logs_mod._pretty_stdout_handler_slot.owned

        user_handler2 = logging.StreamHandler(stream=sys.stdout)
        user_handler2.name = logs_mod._PRETTY_STDOUT_HANDLER_NAME
        logger.addHandler(user_handler2)

        _ = PrettyLoggingObserver()
        assert user_handler2 in logger.handlers
        assert owned_handler not in logger.handlers
    finally:
        logger.handlers[:] = orig_handlers
        logger.setLevel(orig_level)
        logger.propagate = orig_propagate
        logs_mod._pretty_stdout_handler_slot.handler = orig_slot_handler
        logs_mod._pretty_stdout_handler_slot.owned = orig_slot_owned


def test_pretty_logging_observer_handles_non_sized_result() -> None:
    observer = PrettyLoggingObserver()

    observer.on_loader_call(
        LoaderCallEvent(
            loader_name="demo_loader",
            params={},
            result=object(),
            duration=0.1,
        )
    )

    stats = observer._loader_stats["demo_loader"]
    assert stats["calls"] == 1
    assert stats["records"] == 0


def test_pretty_logging_observer_uses_unknown_loader_name_when_empty() -> None:
    observer = PrettyLoggingObserver()

    observer.on_loader_call(LoaderCallEvent(loader_name="", params={}, result={}, duration=0.1))

    assert "<unknown>" in observer._loader_stats


def test_pretty_logging_observer_formats_cache_status() -> None:
    observer = PrettyLoggingObserver()

    observer.on_loader_call(
        LoaderCallEvent(
            loader_name="demo_loader",
            params={},
            result={},
            duration=0.5,
            cache_status="hit",
            field_keys=["order_id"],
        )
    )
    observer.on_loader_call(
        LoaderCallEvent(
            loader_name="demo_loader",
            params={},
            result={},
            duration=0.2,
            cache_status="miss",
            field_keys=None,
        )
    )

    stats = observer._loader_stats["demo_loader"]
    assert stats["cache_hit"] == 1
    assert stats["cache_miss"] == 1


def test_compile_observability_spec_respects_logging_flags() -> None:
    observability = ObservabilityConfig(logging=LoggingConfig(enabled=True, renderer="pretty"))
    spec, observers = compile_observability_spec(observability)
    assert any(isinstance(obs, PrettyLoggingObserver) for obs in observers)
    assert spec.fallback_logger_enabled is True

    observability = ObservabilityConfig(logging=LoggingConfig(enabled=True, renderer="logger"))
    spec, observers = compile_observability_spec(observability)
    assert any(isinstance(obs, LoggingObserver) for obs in observers)
    assert spec.fallback_logger_enabled is True

    spec, observers = compile_observability_spec(ObservabilityConfig(logging=LoggingConfig(enabled=False)))
    assert not any(isinstance(obs, LoggingObserver) for obs in observers)
    assert not any(isinstance(obs, PrettyLoggingObserver) for obs in observers)
    assert spec.fallback_logger_enabled is False

    spec, observers = compile_observability_spec(ObservabilityConfig(logging=LoggingConfig(enabled=True, renderer="unknown")))
    assert any(isinstance(obs, PrettyLoggingObserver) for obs in observers)


def test_compile_observability_spec_includes_optional_observers() -> None:
    observability = ObservabilityConfig(
        logging=LoggingConfig(enabled=False),
        trace=TraceConfig(enabled=True),
        row_gap=RowGapConfig(enabled=True, primary_loader_name="primary", data_loader_names=("a",), sample_limit=2),
        memory_opt=MemoryOptimizationConfig(enabled=True, auto_report=True, max_fields=3),
    )

    _spec, observers = compile_observability_spec(observability)
    assert any(isinstance(obs, ExecutionTraceObserver) for obs in observers)
    assert any(isinstance(obs, RowGapObserver) for obs in observers)
    assert any(isinstance(obs, MemoryOptimizationObserver) for obs in observers)
    assert not any(isinstance(obs, LoggingObserver) for obs in observers)


def test_compile_observability_spec_disables_optional_observers() -> None:
    observability = ObservabilityConfig(
        trace=TraceConfig(enabled=False),
        row_gap=RowGapConfig(enabled=False),
        memory_opt=MemoryOptimizationConfig(enabled=False),
    )

    _spec, observers = compile_observability_spec(observability)
    assert not any(isinstance(obs, ExecutionTraceObserver) for obs in observers)
    assert not any(isinstance(obs, RowGapObserver) for obs in observers)
    assert not any(isinstance(obs, MemoryOptimizationObserver) for obs in observers)


def test_yaml_run_result_to_dataframe_requires_pandas(monkeypatch) -> None:
    main_source = MainSourceIr(source_id="demo", loader=lambda: [])
    demand_ir = DemandIr.from_irs([], [], main_source)
    plan = PlanBuilder(demand_ir).build(targets=[])
    sink = InMemoryRowSink()
    sink.write_row({"id": 1})
    core = ExecutionResult(
        output_path=None,
        total_rows=1,
        duration=0.0,
        demand_ir=demand_ir,
        plan=plan,
    )
    config = DemandConfig(name="demo")
    result = RunResult(core, config=config, yaml_path="demo.yaml", sink=sink)
    assert result.duration == 0.0
    assert result.plan is plan

    with missing_optional_dependency(monkeypatch, "pandas"):
        with pytest.raises(ImportError, match="pandas is required"):
            result.to_dataframe()


def test_yaml_run_result_to_dataframe_requires_in_memory_sink() -> None:
    main_source = MainSourceIr(source_id="demo", loader=lambda: [])
    demand_ir = DemandIr.from_irs([], [], main_source)
    plan = PlanBuilder(demand_ir).build(targets=[])
    core = ExecutionResult(
        output_path=None,
        total_rows=0,
        duration=0.0,
        demand_ir=demand_ir,
        plan=plan,
    )
    config = DemandConfig(name="demo")
    result = RunResult(core, config=config, yaml_path="demo.yaml", sink=None)

    with pytest.raises(ValueError, match=r"in-memory sink"):
        _ = result.to_dataframe()


def test_yaml_run_result_to_dataframe_ok() -> None:
    main_source = MainSourceIr(source_id="demo", loader=lambda: [])
    demand_ir = DemandIr.from_irs([], [], main_source)
    plan = PlanBuilder(demand_ir).build(targets=[])
    sink = InMemoryRowSink()
    sink.write_row({"id": 1})
    core = ExecutionResult(
        output_path=None,
        total_rows=1,
        duration=0.0,
        demand_ir=demand_ir,
        plan=plan,
    )
    config = DemandConfig(name="demo")
    result = RunResult(core, config=config, yaml_path="demo.yaml", sink=sink)
    assert result.duration == 0.0
    assert result.plan is plan

    df = result.to_dataframe()
    assert not df.empty
    assert list(df.columns) == ["id"]


@pytest.mark.parametrize(
    "perf,expected",
    [
        (
            PerformanceConfig(
                enabled=True,
                metrics=("duration",),
                sampling_interval=2,
                report=PerformanceReportConfig(format="json", output="report.json", include_details=True),
                thresholds=PerformanceThresholdsConfig(batch_duration_warn=0.1, memory_increase_warn=1.0),
            ),
            {"format": "json", "include_details": True, "batch_duration_warn": 0.1},
        ),
        (PerformanceConfig(enabled=False, metrics=("duration",), sampling_interval=1), None),
    ],
    ids=["enabled", "disabled"],
)
def test_create_performance_observer_variants(perf, expected) -> None:
    observability = ObservabilityConfig(performance=perf)
    observer = _create_performance_observer_from_config(observability)
    if expected is None:
        assert observer is None
        return
    assert observer is not None
    assert observer.config.report_format == expected["format"]
    assert observer.config.include_details is expected["include_details"]
    assert observer.config.thresholds.batch_duration_warn == expected["batch_duration_warn"]


@pytest.mark.parametrize(
    "relations,expected",
    [
        (
            RelationsConfig(
                enabled=True,
                sampling_rate=0.2,
                log_type_mismatch=False,
                max_samples=10,
                report=RelationReportConfig(format="json", output="rel.json"),
            ),
            {"format": "json", "output_path": "rel.json", "sampling_rate": 0.2, "log_type_mismatch": False},
        ),
        (RelationsConfig(enabled=True, report=RelationReportConfig(format="text", output="rel.json")), {"format": "console"}),
        (RelationsConfig(enabled=False), None),
    ],
    ids=["enabled", "invalid-format", "disabled"],
)
def test_create_relation_observer_variants(relations, expected) -> None:
    observability = ObservabilityConfig(relations=relations)
    observer = _create_relation_observer_from_config(observability)
    if expected is None:
        assert observer is None
        return
    assert observer is not None
    assert observer.config.report_format == expected["format"]
    if "output_path" in expected:
        assert observer.config.output_path == expected["output_path"]
    if "sampling_rate" in expected:
        assert observer.config.sampling_rate == expected["sampling_rate"]
    if "log_type_mismatch" in expected:
        assert observer.config.log_type_mismatch is expected["log_type_mismatch"]


@pytest.mark.parametrize(
    "observability",
    [
        ObservabilityConfig(performance=PerformanceConfig(enabled=True, metrics=("duration",), sampling_interval=1)),
        ObservabilityConfig(relations=RelationsConfig(enabled=True)),
    ],
    ids=["performance", "relations"],
)
def test_compile_observability_spec_registers_observers(observability) -> None:
    _spec, observers = compile_observability_spec(observability)
    assert len(observers) == 1


def test_export_layout_uses_field_ids_when_header_by_field_id() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="order_id", name="Order ID", source=main_source),
            FieldIr(field_id="amount", name="Amount", source=main_source),
        ],
        main_source=main_source,
    )
    layout = export_layout_from_demand_ir(demand_ir, ["order_id", "amount"], header_fields_output_by="field_id")
    assert layout.field_ids == ("order_id", "amount")
    assert layout.header_names is None


def test_export_layout_uses_field_names_when_header_by_name() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="order_id", name="Order ID", source=main_source),
            FieldIr(field_id="amount", name="Amount", source=main_source),
        ],
        main_source=main_source,
    )
    layout = export_layout_from_demand_ir(demand_ir, ["order_id", "amount"], header_fields_output_by="name")
    assert layout.header_names == ("Order ID", "Amount")


def test_export_layout_header_names_none_when_no_mapping() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="order_id", name="order_id", source=main_source),
        ],
        main_source=main_source,
    )
    layout = export_layout_from_demand_ir(demand_ir, ["order_id"], header_fields_output_by="name")
    assert layout.header_names is None
