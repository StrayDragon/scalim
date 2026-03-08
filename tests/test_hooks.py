import json
import logging

import pytest
from scalim.events.event import Event
from scalim.events.events import (
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
)
from scalim.events.catalog import (
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
)
from scalim.hooks.base import HOOK_RAISED_EXCEPTION_WARNING, BaseHook, HookManager
from scalim.ob.observer import EventDispatchObserver, Observer
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.logs import (
    LOGGING_OBSERVER_COLUMN_WRITE_LOG,
    LOGGING_OBSERVER_LOADER_SLIM_LOG,
    LoggingObserver,
)
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink
from scalim.typedefs import DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY


def _get_main_rows(demand, limit: int = 3):
    main_source = demand.main_source
    if main_source is None:
        return []
    params = dict(main_source.params or {})
    if params:
        rows = list(main_source.loader(**params))
    else:
        rows = list(main_source.loader())
    return rows[:limit]


def test_streaming_hooks_capture_events(plan_builder, engine_factory, caplog) -> None:
    targets = ["order_id", "amount", "cost", "profit"]
    plan = plan_builder.build(targets=targets)

    logger = logging.getLogger("scalim.tests.logging_hook")
    observer_manager = ObserverManager()
    observer_manager.register(LoggingObserver(logger=logger))
    perf_observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    observer_manager.register(perf_observer)
    trace_observer = ExecutionTraceObserver()
    observer_manager.register(trace_observer)
    memory_observer = MemoryOptimizationObserver(logger=logger)
    observer_manager.register(memory_observer)

    engine = engine_factory(plan, observer_manager=observer_manager, batch_size=2)

    main_rows = _get_main_rows(plan_builder.demand, limit=3)

    with caplog.at_level(logging.INFO, logger=logger.name):
        engine.run(main_rows=main_rows, sink=InMemoryRowSink())

    assert memory_observer.row_write_events
    assert memory_observer.row_release_events
    assert trace_observer.total_loader_calls > 0
    assert trace_observer.total_row_writes > 0

    metrics = perf_observer.get_metrics()
    assert metrics.batch_count > 0
    assert metrics.loader_stats

    assert caplog.records

    payload = json.loads(trace_observer.export_to_json())
    assert "pipeline" in payload
    assert "batches" in payload

    trace_observer.print_summary()


def test_memory_hook_column_events(plan_builder, engine_factory) -> None:
    targets = ["order_id", "order_source"]
    plan = plan_builder.build(targets=targets)

    memory_observer = MemoryOptimizationObserver()
    observer_manager = ObserverManager(observers=[memory_observer])

    engine = engine_factory(plan, observer_manager=observer_manager, batch_size=2)

    main_rows = _get_main_rows(plan_builder.demand, limit=3)
    engine.run(main_rows=main_rows, sink=InMemoryColumnSink(field_names=targets))

    assert memory_observer.column_write_events
    assert memory_observer.field_slim_events
    assert "order_source" in memory_observer.get_slimmed_fields()
    assert memory_observer.get_columns_written()

    memory_observer.print_summary(max_fields=1)
    memory_observer.reset()
    assert memory_observer.field_slim_events == []


def test_column_trace_and_logging_hooks_capture_field_slim(plan_builder, engine_factory) -> None:
    targets = ["order_id", "order_source"]
    plan = plan_builder.build(targets=targets)

    logger = logging.getLogger("scalim.tests.logging_hook.column")
    observer_manager = ObserverManager()
    observer_manager.register(LoggingObserver(logger=logger))
    trace_observer = ExecutionTraceObserver()
    observer_manager.register(trace_observer)

    engine = engine_factory(plan, observer_manager=observer_manager, batch_size=2)
    main_rows = _get_main_rows(plan_builder.demand, limit=3)
    engine.run(main_rows=main_rows, sink=InMemoryColumnSink(field_names=targets))

    assert trace_observer.total_field_slims > 0
    trace_observer.print_summary()


class _ExplodingHook(BaseHook):
    def on_pipeline_start(self, event) -> None:  # type: ignore[override]
        raise RuntimeError("boom")


class _CaptureHook(BaseHook):
    def __init__(self) -> None:
        self.loader_calls = []
        self.loader_slim_events = []

    def on_loader_call(self, event) -> None:  # type: ignore[override]
        self.loader_calls.append(event)

    def on_loader_slim(self, event) -> None:  # type: ignore[override]
        self.loader_slim_events.append(event)


class _DiagnosticCaptureObserver(EventDispatchObserver):
    def __init__(self) -> None:
        self.events = []

    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        self.events.append(event)


class _PipelineEventCaptureObserver(EventDispatchObserver):
    def __init__(self) -> None:
        self.pipeline_start_events = []
        self.pipeline_end_events = []
        self.batch_start_events = []
        self.batch_end_events = []

    def on_pipeline_start(self, event) -> None:  # type: ignore[override]
        self.pipeline_start_events.append(event)

    def on_pipeline_end(self, event) -> None:  # type: ignore[override]
        self.pipeline_end_events.append(event)

    def on_batch_start(self, event) -> None:  # type: ignore[override]
        self.batch_start_events.append(event)

    def on_batch_end(self, event) -> None:  # type: ignore[override]
        self.batch_end_events.append(event)


class _EventOrderObserver(Observer):
    def __init__(self) -> None:
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event.event_type)


def test_hook_manager_swallows_hook_errors(caplog) -> None:
    hook_manager = HookManager()
    hook_manager.register(_ExplodingHook())

    with caplog.at_level(logging.WARNING, logger="scalim.hooks.base"):
        hook_manager.trigger_pipeline_start(["order_id"], 2)

    expected = HOOK_RAISED_EXCEPTION_WARNING % ("_ExplodingHook", "on_pipeline_start")
    assert any(expected == record.getMessage() for record in caplog.records)


def test_hook_manager_debug_mode_raises() -> None:
    hook_manager = HookManager(enable_debugging=True)
    hook_manager.register(_ExplodingHook())

    with pytest.raises(RuntimeError):
        hook_manager.trigger_pipeline_start(["order_id"], 2)


def test_hook_manager_debug_mode_non_exploding_hook_returns() -> None:
    class _NoopPipelineHook(BaseHook):
        def __init__(self) -> None:
            self.events = []

        def on_pipeline_start(self, event) -> None:  # type: ignore[override]
            self.events.append(event)

    hook = _NoopPipelineHook()
    hook_manager = HookManager(enable_debugging=True)
    hook_manager.register(hook)

    hook_manager.trigger_pipeline_start(["order_id"], 2)

    assert hook.events and hook.events[0].targets == ["order_id"]


def test_hook_manager_emit_on_event_clears_stale_has_hooks_flag() -> None:
    hook_manager = HookManager()
    hook_manager.has_hooks = True
    hook_manager.hooks = []
    hook_manager.on_event_handlers_by_event_type = {}

    hook_manager.emit_on_event(Event(event_type="demo", timestamp=0.0, run_id="r", payload=None))

    assert hook_manager.has_hooks is False


def test_hook_manager_unregister_and_clear() -> None:
    hook = BaseHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    assert hook_manager.unregister(hook) is True
    assert hook_manager.unregister(hook) is False

    hook_manager.register(hook)
    hook_manager.clear()
    assert hook_manager.hooks == []


def test_hook_manager_loader_result_policy_invalid() -> None:
    with pytest.raises(ValueError):
        HookManager(loader_result_policy="bad")


def test_hook_manager_loader_result_policy_summary_and_none() -> None:
    summary_hook = _CaptureHook()
    summary_manager = HookManager(loader_result_policy="summary")
    summary_manager.register(summary_hook)
    summary_manager.trigger_loader_call("loader", {}, [1, 2, 3], 0.1)
    summary = summary_hook.loader_calls[-1].result
    assert summary["type"] == "list"
    assert summary["size"] == 3

    none_hook = _CaptureHook()
    none_manager = HookManager(loader_result_policy="none")
    none_manager.register(none_hook)
    none_manager.trigger_loader_call("loader", {}, {"a": 1}, 0.1)
    assert none_hook.loader_calls[-1].result is None


def test_hook_manager_loader_result_policy_sample_variants() -> None:
    hook = _CaptureHook()
    manager = HookManager(loader_result_policy="sample", loader_result_sample_size=2)
    manager.register(hook)

    manager.trigger_loader_call("loader", {}, {"a": 1, "b": 2, "c": 3}, 0.1)
    assert hook.loader_calls[-1].result == {"a": 1, "b": 2}

    manager.trigger_loader_call("loader", {}, [1, 2, 3], 0.1)
    assert hook.loader_calls[-1].result == [1, 2]

    manager.trigger_loader_call("loader", {}, (1, 2, 3), 0.1)
    assert hook.loader_calls[-1].result == [1, 2]

    manager.trigger_loader_call("loader", {}, set([1, 2, 3]), 0.1)
    assert len(hook.loader_calls[-1].result) == 2

    manager.trigger_loader_call("loader", {}, "abcdef", 0.1)
    assert hook.loader_calls[-1].result == "ab"

    manager.trigger_loader_call("loader", {}, range(5), 0.1)
    assert hook.loader_calls[-1].result == [0, 1]

    manager.trigger_loader_call("loader", {}, object(), 0.1)
    assert hook.loader_calls[-1].result["type"] == "object"

    manager.trigger_loader_slim("loader", 3, ["a", "b"], 1)
    assert hook.loader_slim_events


def test_hook_manager_diagnostic_warning_fallback(caplog) -> None:
    hook_manager = HookManager(fallback_logger_enabled=True)
    with caplog.at_level(logging.WARNING, logger="scalim.hooks.base"):
        hook_manager.trigger_diagnostic_warning(
            message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
            source_id="customers",
            field_id="customer_id",
            lookup_key=1.0,
            row_id=1,
        )
    assert any("诊断" in record.getMessage() for record in caplog.records)


def test_logging_hook_error_context(caplog) -> None:
    logger = logging.getLogger("scalim.tests.logging_error")
    hook = LoggingObserver(logger=logger)

    event = ErrorEvent(RuntimeError("boom"), {"field": "value"})
    with caplog.at_level(logging.ERROR, logger=logger.name):
        hook.on_error(event)

    assert len(caplog.records) >= 2


def test_logging_hook_default_logger() -> None:
    hook = LoggingObserver()
    assert hook.logger is not None


def test_logging_hook_loader_call_len_error(caplog) -> None:
    class _BadLen:
        def __len__(self) -> int:
            raise TypeError("bad len")

    logger = logging.getLogger("scalim.tests.logging_len_error")
    hook = LoggingObserver(logger=logger)
    event = LoaderCallEvent(loader_name="loader", params={}, result=_BadLen(), duration=0.1)
    with caplog.at_level(logging.INFO, logger=logger.name):
        hook.on_loader_call(event)

    assert any("返回: 0" in record.getMessage() for record in caplog.records)


def test_logging_hook_diagnostic_warning(caplog) -> None:
    logger = logging.getLogger("scalim.tests.logging_warning")
    hook = LoggingObserver(logger=logger)

    event = DiagnosticWarningEvent(
        message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
        source_id="customers",
        field_id="customer_name",
        lookup_key=1.0,
        row_id=0,
    )
    with caplog.at_level(logging.WARNING, logger=logger.name):
        hook.on_diagnostic_warning(event)

    assert any("诊断" in record.getMessage() for record in caplog.records)


def test_memory_observer_close_auto_report(caplog) -> None:
    logger = logging.getLogger("scalim.tests.memory_close")
    observer = MemoryOptimizationObserver(logger=logger, auto_report=True, max_fields=1)
    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.close()
    assert caplog.records


def test_hook_manager_triggers_loader_and_column_events(caplog) -> None:
    logger = logging.getLogger("scalim.tests.logging_debug")
    observer = LoggingObserver(logger=logger)
    observer_manager = ObserverManager(observers=[observer])

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        observer_manager.emit_loader_slim("loader_x", 3, ["a"], batch_num=1)
        observer_manager.emit_column_write("field_x", 2, batch_num=1)

    messages = [record.getMessage() for record in caplog.records]
    assert any(LOGGING_OBSERVER_LOADER_SLIM_LOG.split("%s")[0] in message for message in messages)
    assert any(LOGGING_OBSERVER_COLUMN_WRITE_LOG.split("%s")[0] in message for message in messages)


def test_hook_manager_diagnostic_warning_sampled_once() -> None:
    observer = _DiagnosticCaptureObserver()
    observer_manager = ObserverManager(observers=[observer])

    observer_manager.emit_diagnostic_warning(
        message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
        source_id="customers",
        field_id="customer_name",
        lookup_key=1.0,
        row_id=0,
        sample_once=True,
    )
    observer_manager.emit_diagnostic_warning(
        message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
        source_id="customers",
        field_id="customer_name",
        lookup_key=2.0,
        row_id=1,
        sample_once=True,
    )

    assert len(observer.events) == 1
    assert observer.events[0].source_id == "customers"


def test_hook_manager_diagnostic_warning_fallback_logger(caplog) -> None:
    manager = ObserverManager(fallback_logger_enabled=True)

    with caplog.at_level(logging.WARNING, logger="scalim.ob.manager"):
        manager.emit_diagnostic_warning(
            message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
            source_id="customers",
            field_id="customer_name",
            lookup_key=1.0,
            row_id=0,
            sample_once=True,
        )

    assert any("诊断" in record.getMessage() for record in caplog.records)

    caplog.clear()
    quiet_manager = ObserverManager(fallback_logger_enabled=False)
    with caplog.at_level(logging.WARNING, logger="scalim.ob.manager"):
        quiet_manager.emit_diagnostic_warning(
            message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
            source_id="customers",
            field_id="customer_name",
            lookup_key=1.0,
            row_id=0,
            sample_once=True,
        )

    assert not caplog.records


def test_seq_pipeline_emits_pipeline_and_batch_events(plan_builder, engine_factory) -> None:
    targets = ["order_id", "amount"]
    plan = plan_builder.build(targets=targets)

    observer = _PipelineEventCaptureObserver()
    observer_manager = ObserverManager(observers=[observer])

    engine = engine_factory(plan, observer_manager=observer_manager, batch_size=2)

    main_rows = _get_main_rows(plan_builder.demand, limit=3)
    engine.run(main_rows=main_rows, sink=InMemoryRowSink())

    assert observer.pipeline_start_events
    assert observer.pipeline_end_events
    assert observer.pipeline_start_events[0].targets == targets
    assert observer.pipeline_start_events[0].batch_size == 2
    assert observer.pipeline_end_events[0].total_batches == 2
    assert observer.batch_start_events[0].row_ids == [0, 1]
    assert observer.batch_start_events[1].row_ids == [2]
    assert len(observer.batch_start_events) == len(observer.batch_end_events) == 2


def test_seq_pipeline_emits_event_order(plan_builder, engine_factory) -> None:
    targets = ["order_id", "amount"]
    plan = plan_builder.build(targets=targets)

    observer = _EventOrderObserver()
    observer_manager = ObserverManager(observers=[observer])

    engine = engine_factory(plan, observer_manager=observer_manager, batch_size=2)
    main_rows = _get_main_rows(plan_builder.demand, limit=3)
    engine.run(main_rows=main_rows, sink=InMemoryRowSink())

    events = observer.events
    assert events
    assert events[0] == EVENT_PIPELINE_START
    assert events[-1] == EVENT_PIPELINE_END

    batch_starts = [idx for idx, name in enumerate(events) if name == EVENT_BATCH_START]
    batch_ends = [idx for idx, name in enumerate(events) if name == EVENT_BATCH_END]
    assert len(batch_starts) == len(batch_ends) > 0
    assert batch_starts[0] > 0
    assert batch_ends[-1] < len(events) - 1
    for start_idx, end_idx in zip(batch_starts, batch_ends):
        assert start_idx < end_idx


def test_memory_optimization_hook_summary_truncates(caplog) -> None:
    hook = MemoryOptimizationObserver()

    hook.on_field_slim(FieldSlimEvent(field_key="a", reason="test", batch_num=1, remaining_fields=1))
    hook.on_field_slim(FieldSlimEvent(field_key="b", reason="test", batch_num=1, remaining_fields=1))
    hook.on_column_write(ColumnWriteEvent(field_key="c1", row_count=1, batch_num=1))
    hook.on_column_write(ColumnWriteEvent(field_key="c2", row_count=1, batch_num=1))
    hook.on_loader_slim(LoaderSlimEvent(loader_name="loader", original_keys=3, extracted_fields=["a"], batch_num=1))

    with caplog.at_level(logging.INFO, logger=hook._logger.name):
        hook.print_summary(max_fields=1)

    assert hook.loader_slim_events
