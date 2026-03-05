import csv
from pathlib import Path

import pytest

from scalim.dsl.by_yaml import OutputOverrides, RunOverrides, RunResult, run
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
from scalim.events.catalog import EVENT_PIPELINE_START
from scalim.events.events import BatchEndEvent, BatchStartEvent, LoaderCallEvent, PipelineEndEvent, PipelineStartEvent
from scalim.hooks.base import BaseHook
from scalim.ob.observer import Observer
from scalim.ob.presets.logs import LoggingObserver, PrettyLoggingObserver
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim.ob.presets.row_gap import RowGapObserver
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr
from tests.testing_utils import missing_optional_dependency

_ALLOWED_MODULES = frozenset(["scalim_misc.example_report_ir"])


def _demo_yaml_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "order_report.yaml"


def _write_yaml_without_output(tmp_path: Path, source_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    content = content.replace("path: ./.tmp/output/order_report.csv", 'path: ""')
    output_path = tmp_path / "order_report_no_output.yaml"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _write_yaml_with_column_output(tmp_path: Path, source_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    content = content.replace("streaming: true", "streaming: false")
    output_path = tmp_path / "order_report_column.yaml"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _write_yaml_with_output_path(tmp_path: Path, source_path: Path, output_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    content = content.replace("path: ./.tmp/output/order_report.csv", 'path: "{}"'.format(output_path))
    yaml_path = tmp_path / "order_report_custom_output.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def _write_yaml_with_named_headers(tmp_path: Path, source_path: Path, output_path: Path) -> Path:
    content = source_path.read_text(encoding="utf-8")
    content = content.replace(
        "include_header: true",
        "include_header: true\n  header_fields_output_by: name",
        1,
    )
    content = content.replace("path: ./.tmp/output/order_report.csv", 'path: "{}"'.format(output_path))
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
        (
            _build_column_yaml,
            "order_report_column.csv",
            None,
            False,
        ),
    ],
    ids=["default-streaming", "column-default-return"],
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
        overrides=RunOverrides(output=OutputOverrides(path=str(output_path))),
        sink=sink,
    )

    assert result.total_rows > 0
    assert output_path.exists()
    assert result.output_path == str(output_path)
    if sink is not None:
        assert sink.get_data()

    if check_header:
        header = output_path.read_text(encoding="utf-8").splitlines()[0]
        assert "order_id" in header


def test_run_header_fields_output_by_name_uses_field_names(example_model, tmp_path: Path) -> None:
    output_path = tmp_path / "order_report_named.csv"
    yaml_path = _write_yaml_with_named_headers(tmp_path, _demo_yaml_path(), output_path)

    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(output=OutputOverrides(path=str(output_path))),
    )

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        first_row = next(reader)

    output_fields = list(result.config.output.fields) if result.config.output and result.config.output.fields else []
    export_layout = export_layout_from_demand_ir(result.demand_ir, output_fields, header_fields_output_by="name")
    expected_headers = list(export_layout.header_names or export_layout.field_ids)
    assert header == expected_headers
    assert first_row[0] != ""


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
        overrides=RunOverrides(output=OutputOverrides(path=str(output_path))),
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
        overrides=RunOverrides(output=OutputOverrides(path=str(output_path))),
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
    assert "Scalim Pipeline" in output
    assert "Loader" in output


def test_pretty_logging_observer_renders_batch_duration_from_event(capsys) -> None:
    observer = PrettyLoggingObserver()

    observer.on_pipeline_start(PipelineStartEvent(targets=["a"], batch_size=1))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=1.23))

    output = capsys.readouterr().out
    assert "1.23s" in output


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

    assert observer._loader_stats[-1]["count"] == 0


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

    names = [stat["name"] for stat in observer._loader_stats]
    assert names == ["demo_loader [cache:hit fields:order_id]", "demo_loader [cache:miss]"]


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
