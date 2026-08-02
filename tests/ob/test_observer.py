import logging
import sys
import tempfile
import warnings
from pathlib import Path

import pytest

from scalim.events._events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    FieldComputeEvent,
    LoaderCallEvent,
    OperatorSpanEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from scalim.events import Event, EventType, get_event_catalog, get_event_catalog_map
from scalim.ob._internal.common import ObserverManagerMode
from scalim.ob.observability import Observability
from scalim.ob.observer import EventDispatchObserver, Observer
from scalim.ob.manager import (
    OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING,
    OBSERVER_RAISED_EXCEPTION_WARNING,
    ObserverManager,
)
from scalim.ob.presets.performance_presentation import PerformancePresentationLayer
from scalim.ob.presets.performance import (
    PSUTIL_NOT_INSTALLED_WARNING_PREFIX,
    PerformanceConfig,
    PerformanceObserver,
    PerformanceThresholds,
)
from scalim.execution.runtime_bindings import RuntimeBindings
from tests.support.testing_utils import missing_optional_dependency
from tests.support.event_envelope import event_envelope


def _get_main_rows(demand, runtime_bindings: RuntimeBindings, limit: int = 3):
    main_source = demand.main_source
    if main_source is None:
        return []
    params = dict(main_source.params or {})
    if params:
        rows = list(runtime_bindings.require_main_source_loader(main_source.source_id)(**params))
    else:
        rows = list(runtime_bindings.require_main_source_loader(main_source.source_id)())
    return rows[:limit]


def _build_engine_with_observer(plan_builder, engine_factory, **config_kwargs):
    targets = ["order_id", "amount"]
    plan = plan_builder.build(targets=targets)

    metrics = config_kwargs.pop("metrics", {"duration"})
    config = PerformanceConfig(metrics=metrics, report_format=config_kwargs.pop("report_format", "none"), **config_kwargs)
    observer = PerformanceObserver(config=config)

    observer_manager = ObserverManager(observers=[observer])

    engine = engine_factory(plan, observer_manager=observer_manager, batch_size=2)
    return engine, observer


def test_event_catalog_includes_core_events() -> None:
    catalog = get_event_catalog()
    assert catalog

    catalog_map = get_event_catalog_map()
    required = [
        EventType.PIPELINE_START,
        EventType.PIPELINE_END,
        EventType.BATCH_START,
        EventType.BATCH_END,
        EventType.LOADER_CALL,
        EventType.ERROR,
        EventType.DIAGNOSTIC_WARNING,
        EventType.ROW_WRITE,
        EventType.ROW_RELEASE,
        EventType.FIELD_SLIM,
    ]
    for name in required:
        assert name in catalog_map
        descriptor = catalog_map[name]
        assert descriptor.name
        assert descriptor.summary
        assert descriptor.key_fields
        assert descriptor.volume in ("lite", "full")
        assert descriptor.payload_policy


def test_performance_observer_basic(plan_builder, engine_factory, example_runtime_bindings) -> None:
    engine, observer = _build_engine_with_observer(plan_builder, engine_factory)
    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    engine.run(main_rows=main_rows)

    metrics = observer.get_metrics()
    assert metrics.batch_count == 2
    assert metrics.total_rows == 3
    assert metrics.total_duration > 0
    assert len(metrics.batch_durations) == 2
    assert metrics.throughput > 0


def test_performance_observer_resets_metrics_each_run(plan_builder, engine_factory, example_runtime_bindings) -> None:
    engine, observer = _build_engine_with_observer(plan_builder, engine_factory)
    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    engine.run(main_rows=main_rows)
    assert observer.metrics.total_rows == 3
    assert observer.metrics.batch_count == 2

    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=1)
    engine.run(main_rows=main_rows)
    assert observer.metrics.total_rows == 1
    assert observer.metrics.batch_count == 1


def test_performance_observer_loader_stats(plan_builder, engine_factory) -> None:
    engine, observer = _build_engine_with_observer(plan_builder, engine_factory)
    engine.run()

    metrics = observer.get_metrics()
    assert len(metrics.loader_stats) > 0
    for name, stats in metrics.loader_stats.items():
        assert stats.call_count > 0


def test_performance_observer_cache_metrics_counts() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    stats = observer.metrics.get_loader_stats("loader")

    event_miss = event_envelope(
        LoaderCallEvent(
            loader_name="loader",
            params={},
            result={1: {"x": 1}},
            duration=0.1,
            cache_status="miss",
        )
    )
    event_hit = event_envelope(
        LoaderCallEvent(
            loader_name="loader",
            params={},
            result={1: {"x": 1}},
            duration=0.0,
            cache_status="hit",
        )
    )
    event_no_cache = event_envelope(
        LoaderCallEvent(
            loader_name="loader",
            params={},
            result={1: {"x": 1}},
            duration=0.2,
            cache_status=None,
        )
    )

    observer.on_loader_call(event_miss)
    observer.on_loader_call(event_hit)
    observer.on_loader_call(event_no_cache)

    assert stats.call_count == 3
    assert stats.exec_count == 2
    assert stats.cache_miss_count == 1
    assert stats.cache_hit_count == 1
    assert stats.cache_hit_rate == 0.5


def test_performance_observer_console_output(plan_builder, engine_factory, example_runtime_bindings, caplog) -> None:
    logger = logging.getLogger("scalim.tests.observer")
    engine, _observer = _build_engine_with_observer(
        plan_builder,
        engine_factory,
        report_format="console",
        include_loader_top_n=5,
        logger=logger,
    )

    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    with caplog.at_level(logging.INFO, logger=logger.name):
        engine.run(main_rows=main_rows)

    assert any("[scalim] performance:" in record.getMessage() and "summary" in record.getMessage() for record in caplog.records)
    assert any("total_duration_s=" in record.getMessage() for record in caplog.records)


def test_performance_observer_print_summary_details(caplog) -> None:
    logger = logging.getLogger("scalim.tests.observer.details")
    config = PerformanceConfig(
        metrics={"duration"},
        report_format="console",
        include_loader_stats=True,
        logger=logger,
    )
    observer = PerformanceObserver(config=config)

    observer.metrics.total_duration = 1.0
    observer.metrics.total_rows = 10
    observer.metrics.batch_count = 1
    observer.metrics.batch_durations = [1.0]
    observer.metrics.stage_metrics.loader_duration = 0.1
    observer.metrics.stage_metrics.compute_duration = 0.2
    observer.metrics.stage_metrics.write_duration = 0.3
    stats = observer.metrics.get_loader_stats("orders")
    stats.record_call(duration=0.1, record_count=10)

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.print_summary()

    assert any("[scalim] performance:" in record.getMessage() and "summary" in record.getMessage() for record in caplog.records)
    assert any("stage" in record.getMessage() for record in caplog.records)
    assert any("loader" in record.getMessage() for record in caplog.records)


def test_performance_observer_json_output(plan_builder, engine_factory, example_runtime_bindings) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = str(Path(tmpdir) / "perf_report.json")

        engine, _observer = _build_engine_with_observer(
            plan_builder,
            engine_factory,
            report_format="json",
            output_path=output_path,
        )

        main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
        engine.run(main_rows=main_rows)

        assert Path(output_path).exists()
        content = Path(output_path).read_text(encoding="utf-8")
        assert "summary" in content


def test_performance_observer_csv_output(plan_builder, engine_factory, example_runtime_bindings) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = str(Path(tmpdir) / "perf_report.csv")

        engine, _observer = _build_engine_with_observer(
            plan_builder,
            engine_factory,
            report_format="csv",
            output_path=output_path,
        )

        main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
        engine.run(main_rows=main_rows)

        assert Path(output_path).exists()
        content = Path(output_path).read_text(encoding="utf-8")
        assert "batch_num" in content
        assert "duration" in content


def test_performance_observer_threshold_warning(plan_builder, engine_factory, example_runtime_bindings, caplog) -> None:
    logger = logging.getLogger("scalim.tests.threshold")
    thresholds = PerformanceThresholds(batch_duration_warn=0.0)
    engine, _observer = _build_engine_with_observer(
        plan_builder,
        engine_factory,
        thresholds=thresholds,
        logger=logger,
    )

    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    with caplog.at_level(logging.WARNING, logger=logger.name):
        engine.run(main_rows=main_rows)

    assert any("批次耗时超阈值" in record.getMessage() for record in caplog.records)


def test_performance_observer_threshold_callback(plan_builder, engine_factory, example_runtime_bindings) -> None:
    exceeded_metrics = []

    def on_exceeded(metric_name: str, value: object) -> None:
        exceeded_metrics.append((metric_name, value))

    thresholds = PerformanceThresholds(batch_duration_warn=0.0)
    engine, _observer = _build_engine_with_observer(
        plan_builder,
        engine_factory,
        thresholds=thresholds,
    )
    _observer._on_threshold_exceeded = on_exceeded

    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    engine.run(main_rows=main_rows)

    assert len(exceeded_metrics) > 0
    assert exceeded_metrics[0][0] == "batch_duration"


def test_performance_observer_reset(plan_builder, engine_factory, example_runtime_bindings) -> None:
    engine, observer = _build_engine_with_observer(plan_builder, engine_factory)

    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    engine.run(main_rows=main_rows)
    assert observer.get_metrics().batch_count > 0

    observer.reset()
    assert observer.get_metrics().batch_count == 0
    assert len(observer.get_metrics().batch_durations) == 0


def test_performance_config_default() -> None:
    config = PerformanceConfig.default()
    assert "duration" in config.metrics
    assert config.report_format == "console"


def test_performance_config_full() -> None:
    config = PerformanceConfig.full()
    assert "duration" in config.metrics
    assert "memory" in config.metrics
    assert "cpu" in config.metrics
    assert config.include_batch_lines is True
    assert config.include_loader_stats is True


def test_performance_observer_default_config() -> None:
    observer = PerformanceObserver()
    assert "duration" in observer.config.metrics


def test_performance_observer_event_types_include_operator_span_when_enabled() -> None:
    logger = logging.getLogger("scalim.tests.operator_span")
    disabled = PerformanceObserver(
        config=PerformanceConfig(metrics={"duration"}, report_format="none", include_field_compute_top_n=0, logger=logger)
    )
    assert EventType.OPERATOR_SPAN not in (disabled.event_types or set())

    enabled = PerformanceObserver(
        config=PerformanceConfig(metrics={"duration"}, report_format="none", include_field_compute_top_n=3, logger=logger)
    )
    assert EventType.OPERATOR_SPAN in (enabled.event_types or set())


def test_performance_observer_field_compute_profiling_reports_top(caplog) -> None:
    logger = logging.getLogger("scalim.tests.field_top")
    observer = PerformanceObserver(
        config=PerformanceConfig(
            metrics={"duration"},
            report_format="console",
            include_field_compute_top_n=2,
            logger=logger,
        )
    )

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["a"], batch_size=2)))
    observer.on_operator_span(event_envelope(OperatorSpanEvent(operator_type="compute", field_key="a", batch_num=1, duration=0.2)))
    observer.on_operator_span(event_envelope(OperatorSpanEvent(operator_type="compute", field_key="b", batch_num=1, duration=0.1)))

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.5)))

    assert any("field_top" in record.getMessage() for record in caplog.records)


def test_performance_observer_warns_when_psutil_missing(monkeypatch) -> None:
    config = PerformanceConfig(metrics={"memory", "cpu"}, report_format="none")
    with missing_optional_dependency(monkeypatch, "psutil"):
        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            _ = PerformanceObserver(config=config)

        assert any(PSUTIL_NOT_INSTALLED_WARNING_PREFIX in str(record.message) for record in records)


def test_performance_observer_init_with_fake_psutil(monkeypatch) -> None:
    config = PerformanceConfig(metrics={"cpu"}, report_format="none")

    class _Proc:
        def cpu_percent(self):  # type: ignore[no-untyped-def]
            return 0.0

    class _FakePsutil:
        @staticmethod
        def Process():  # type: ignore[no-untyped-def]
            return _Proc()

    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())
    observer = PerformanceObserver(config=config)

    assert observer.metrics.cpu_samples == []


def test_performance_observer_memory_cpu_error_paths() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    observer._has_psutil = True

    class _BadProcess:
        def memory_info(self):
            raise OSError("boom")

        def cpu_percent(self):
            raise AttributeError("boom")

    observer._process = _BadProcess()

    assert observer._get_memory_mb() is None
    assert observer._get_cpu_percent() is None


def test_performance_observer_samples_cpu() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    observer.metrics.cpu_samples = []

    observer._get_cpu_percent = lambda: 12.5  # type: ignore[assignment]
    observer._sample_cpu("batch_1")

    assert observer.metrics.cpu_samples


def test_performance_observer_memory_threshold_warning(caplog) -> None:
    logger = logging.getLogger("scalim.tests.memory_threshold")
    thresholds = PerformanceThresholds(memory_increase_warn=1.0)
    config = PerformanceConfig(metrics={"duration"}, report_format="none", thresholds=thresholds, logger=logger)
    observer = PerformanceObserver(config=config)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        observer._check_thresholds("memory_increase", 10.0)

    assert any("[scalim] performance:" in record.getMessage() and "memory_increase_mb" in record.getMessage() for record in caplog.records)


def test_performance_observer_details_and_events(caplog) -> None:
    logger = logging.getLogger("scalim.tests.details")
    config = PerformanceConfig(metrics={"duration"}, report_format="console", include_batch_lines=True, logger=logger)
    observer = PerformanceObserver(config=config)
    observer.config.metrics = {"duration", "memory", "cpu"}
    observer._has_psutil = True

    class _MemInfo:
        rss = 10 * 1024 * 1024

    class _Proc:
        def memory_info(self):  # type: ignore[no-untyped-def]
            return _MemInfo()

        def cpu_percent(self):  # type: ignore[no-untyped-def]
            return 5.0

    observer._process = _Proc()

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["a"], batch_size=2)))
    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1, 2])))
    observer.on_loader_call(event_envelope(LoaderCallEvent(loader_name="demo", params={}, result={}, duration=0.01)))
    observer.on_field_compute(event_envelope(FieldComputeEvent(field_key="a", row_id=1, dependencies={}, result=1)))

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.1)))

    observer.on_row_write(event_envelope(RowWriteEvent(row_id=1, field_count=1, batch_num=1, row_index=0)))
    observer.on_column_write(event_envelope(ColumnWriteEvent(field_key="a", row_count=1, batch_num=1)))


def test_performance_observer_stage_metrics_from_spans() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["a"], batch_size=2)))
    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1, 2])))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=1, duration=0.4)))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="compute", batch_num=1, duration=0.6)))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="write", batch_num=1, duration=0.5)))
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=1.5)))
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=1.5)))

    stages = observer.get_metrics().stage_metrics
    assert stages.loader_duration == pytest.approx(0.4)
    assert stages.compute_duration == pytest.approx(0.6)
    assert stages.write_duration == pytest.approx(0.5)
    assert stages.loader_duration + stages.compute_duration + stages.write_duration <= observer.get_metrics().total_duration


def test_performance_observer_stage_metrics_negative_duration_clamped() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))

    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1])))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=1, duration=-1.0)))
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.1)))

    stages = observer.get_metrics().stage_metrics
    assert stages.loader_duration == 0.0


def test_performance_observer_stage_metrics_multi_batch() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["a"], batch_size=2)))

    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1, 2])))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=1, duration=0.2)))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="compute", batch_num=1, duration=0.3)))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="write", batch_num=1, duration=0.1)))
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.8)))

    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=2, row_ids=[3, 4])))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="loader", batch_num=2, duration=0.3)))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="compute", batch_num=2, duration=0.4)))
    observer.on_stage_span(event_envelope(StageSpanEvent(stage="write", batch_num=2, duration=0.2)))
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=2, duration=1.2)))

    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=2, total_duration=2.0)))

    stages = observer.get_metrics().stage_metrics
    assert stages.loader_duration == pytest.approx(0.5)
    assert stages.compute_duration == pytest.approx(0.7)
    assert stages.write_duration == pytest.approx(0.3)
    assert stages.loader_duration + stages.compute_duration + stages.write_duration <= observer.get_metrics().total_duration


def test_performance_observer_json_report_paths(tmp_path: Path, caplog, monkeypatch) -> None:
    logger = logging.getLogger("scalim.tests.json_report")
    config = PerformanceConfig(metrics={"duration"}, report_format="json", logger=logger)
    observer = PerformanceObserver(config=config)

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer._write_json_report()

    output_path = tmp_path / "nested" / "report.json"
    observer.config.output_path = str(output_path)
    observer._write_json_report()
    assert output_path.exists()

    def _raise_write(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_text", _raise_write)
    with caplog.at_level(logging.WARNING, logger=logger.name):
        observer._write_json_report()


def test_performance_observer_csv_report_paths(tmp_path: Path, caplog, monkeypatch) -> None:
    logger = logging.getLogger("scalim.tests.csv_report")
    config = PerformanceConfig(metrics={"duration"}, report_format="csv", logger=logger)
    observer = PerformanceObserver(config=config)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        observer._write_csv_report()

    observer.config.output_path = str(tmp_path / "empty.csv")
    observer.metrics.to_csv_rows = lambda: []  # type: ignore[assignment]
    observer._write_csv_report()

    output_path = tmp_path / "nested" / "report.csv"
    observer.config.output_path = str(output_path)
    observer.metrics.to_csv_rows = lambda: [{"batch_num": 1, "duration": 0.1}]  # type: ignore[assignment]
    observer._write_csv_report()
    assert output_path.exists()

    def _raise_open(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    monkeypatch.setattr(Path, "open", _raise_open)
    with caplog.at_level(logging.WARNING, logger=logger.name):
        observer._write_csv_report()


def test_performance_observer_print_summary_memory(caplog) -> None:
    logger = logging.getLogger("scalim.tests.summary")
    config = PerformanceConfig(metrics={"duration"}, report_format="none", logger=logger)
    observer = PerformanceObserver(config=config)
    observer.metrics.total_duration = 1.0
    observer.metrics.total_rows = 2
    observer.metrics.batch_count = 1
    observer.metrics.batch_durations = [0.1]
    observer.metrics.peak_memory_mb = 10.0
    observer.metrics.start_memory_mb = 1.0
    observer.metrics.end_memory_mb = 3.0

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.print_summary()

    assert any("peak_memory_mb=" in record.getMessage() for record in caplog.records)
    assert any("memory_increase_mb=" in record.getMessage() for record in caplog.records)


def test_performance_observer_reset_initializes_samples() -> None:
    config = PerformanceConfig(metrics={"duration"}, report_format="none")
    observer = PerformanceObserver(config=config)
    observer.config.metrics = {"duration", "memory", "cpu"}
    observer._has_psutil = True

    observer.reset()

    assert observer.metrics.memory_samples == []
    assert observer.metrics.cpu_samples == []


def _has_psutil() -> bool:
    try:
        import psutil  # noqa: F401, PLC0415

        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _has_psutil(),
    reason="psutil not installed",
)
def test_performance_observer_with_memory(plan_builder, engine_factory, example_runtime_bindings) -> None:
    engine, observer = _build_engine_with_observer(
        plan_builder,
        engine_factory,
        metrics={"duration", "memory"},
    )
    main_rows = _get_main_rows(plan_builder.demand, example_runtime_bindings, limit=3)
    engine.run(main_rows=main_rows)

    metrics = observer.get_metrics()
    assert metrics.memory_samples is not None
    assert len(metrics.memory_samples) > 0
    assert metrics.peak_memory_mb is not None


class _ExplodingObserver(Observer):
    def on_event(self, event) -> None:  # type: ignore[override]
        raise RuntimeError("boom")

    def close(self) -> None:  # type: ignore[override]
        raise RuntimeError("close boom")


class _CaptureObserver(Observer):
    def __init__(self) -> None:
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_observer_manager_swallows_errors(caplog) -> None:
    observer = _ExplodingObserver()
    manager = ObserverManager(observers=[observer])

    with caplog.at_level(logging.WARNING, logger="scalim.ob.manager"):
        manager.emit_event(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1))

    expected = OBSERVER_RAISED_EXCEPTION_WARNING % ("_ExplodingObserver", "on_event")
    assert any(expected == record.getMessage() for record in caplog.records)


def test_observer_manager_debug_mode_raises() -> None:
    observer = _ExplodingObserver()
    manager = ObserverManager(observers=[observer], enable_debugging=True)

    with pytest.raises(RuntimeError):
        manager.emit_event(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1))


def test_observer_manager_unregister_clear_and_drain() -> None:
    observer = _CaptureObserver()
    manager = ObserverManager(observers=[observer], mode=ObserverManagerMode.CAPTURE)

    manager.emit_event(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1))
    assert manager.drain_events()
    assert manager.drain_events() == []

    manager.clear()
    assert manager.observers == []
    assert manager.drain_events() == []

    manager.register(observer)
    assert manager.unregister(observer) is True
    assert manager.unregister(observer) is False


def test_observer_manager_skips_unsupported_events() -> None:
    observer = _CaptureObserver()
    observer.event_types = {EventType.PIPELINE_START}
    manager = ObserverManager(observers=[observer])

    manager.emit_event(EventType.PIPELINE_END, PipelineEndEvent(total_batches=0, total_duration=0.0))
    assert observer.events == []


def test_observer_manager_swallows_supports_errors() -> None:
    class _ExplodingSupportsObserver(Observer):
        def __init__(self) -> None:
            self.events = []

        def supports(self, event_type: str) -> bool:  # noqa: ARG002
            raise RuntimeError("boom supports")

        def on_event(self, event) -> None:  # type: ignore[override]
            self.events.append(event)

    observer = _ExplodingSupportsObserver()
    manager = ObserverManager(observers=[observer])

    manager.emit_event(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1))
    assert observer.events == []


def test_observer_manager_close_handles_errors(caplog) -> None:
    observer = _ExplodingObserver()
    manager = ObserverManager(observers=[observer])

    with caplog.at_level(logging.WARNING, logger="scalim.ob.manager"):
        manager.close()

    expected = OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING % "_ExplodingObserver"
    assert any(expected == record.getMessage() for record in caplog.records)


def test_observer_manager_close_skips_without_close() -> None:
    class _NoCloseObserver:
        def on_event(self, event) -> None:  # type: ignore[no-untyped-def]
            _ = event

    manager = ObserverManager()
    manager.register(_NoCloseObserver())  # type: ignore[arg-type]
    manager.close()


def test_observer_manager_close_debug_mode_raises() -> None:
    observer = _ExplodingObserver()
    manager = ObserverManager(observers=[observer], enable_debugging=True)

    with pytest.raises(RuntimeError):
        manager.close()


def test_observability_register_builds_manager() -> None:
    observer = _CaptureObserver()
    observability = Observability()
    observability.register(observer)
    manager = observability.build_manager()
    assert observer in manager.observers


def test_event_dispatch_observer_ignores_unknown_event() -> None:
    observer = EventDispatchObserver()
    event = Event(event_type="unknown", timestamp=0.0, run_id="run", payload=None, meta={}, seq=0)
    observer.on_event(event)


def test_event_dispatch_observer_caches_handler_callable() -> None:
    class _CaptureObserver(EventDispatchObserver):
        def __init__(self) -> None:
            self.calls = 0

        def on_pipeline_start(self, event: PipelineStartEvent) -> None:  # type: ignore[override]
            self.calls += 1

    observer = _CaptureObserver()
    payload = PipelineStartEvent(targets=["a"], batch_size=1)
    event = Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="run", payload=payload, meta={}, seq=0)

    observer.on_event(event)
    observer.dispatch_map = {EventType.PIPELINE_START: "missing"}  # type: ignore[assignment]
    observer.on_event(event)

    assert observer.calls == 2


def test_event_dispatch_observer_caches_none_for_missing_handler() -> None:
    class _MissingHandlerObserver(EventDispatchObserver):
        dispatch_map = {"x": "missing"}

    observer = _MissingHandlerObserver()
    event = Event(event_type="x", timestamp=0.0, run_id="run", payload=None, meta={}, seq=0)

    observer.on_event(event)
    assert observer._handler_cache["x"] is None  # noqa: SLF001

    observer.on_event(event)


def test_event_to_dict_with_dataclass_payload() -> None:
    payload = PipelineStartEvent(targets=["a"], batch_size=1)
    event = Event(event_type=EventType.PIPELINE_START, timestamp=1.0, run_id="run", payload=payload, meta={"x": 1}, seq=2)
    data = event.to_dict()
    assert data["payload"]["targets"] == ["a"]
    assert data["meta"]["x"] == 1


def test_performance_observer_presentation_layer_is_replaceable() -> None:
    class _CapturePresentation(PerformancePresentationLayer):
        def __init__(self) -> None:
            self.called = False

        def output_report(self, **kwargs) -> None:  # type: ignore[override,no-untyped-def]
            self.called = True
            assert kwargs["metrics"].batch_count == 1
            assert kwargs["metrics"].total_duration == 0.2

    presentation = _CapturePresentation()
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="console", presentation=presentation))

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["x"], batch_size=1)))
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.2)))

    assert observer.get_metrics().batch_count == 1
    assert presentation.called is True
