import logging

import pytest
from scalim._internal.utils.loader_result import LoaderResultPolicy
from scalim.events import Event, EventType
from scalim.events._events import PipelineStartEvent, StageSpanEvent
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.hooks import BaseHook, HookManager
from scalim.ob.hub import InstrumentationHub
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.ob.presets.logs import LoggingObserver
from scalim.ob.presets.performance import PerformanceObserver
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan, PlanMetadata, Stage
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.spec.ir import (
    CallBySpecIr,
    CallByValueIr,
    DerivedFieldIr,
    FieldIr,
    MainSourceIr,
    RuntimeHandleIdIr,
)


class _CaptureOnEventHook(BaseHook):
    def __init__(self) -> None:
        self.events = []

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)


class _CaptureSubsetOnEventHook(_CaptureOnEventHook):
    event_types = {EventType.PIPELINE_START}


class _CaptureObserver(Observer):
    event_types = {EventType.PIPELINE_START}

    def __init__(self) -> None:
        self.events = []

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_hub_emit_lazy_does_not_call_factory_when_unwanted() -> None:
    hub = InstrumentationHub()

    def _factory():  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected payload factory call")

    assert hub.emit_lazy(EventType.PIPELINE_START, _factory) is None


def test_hub_emit_field_compute_short_circuits_when_unwanted() -> None:
    hub = InstrumentationHub()
    hub.emit_field_compute(field_key="f", row_id=1, dependencies={}, result=1)


def test_hub_emit_loader_retry_short_circuits_when_unwanted() -> None:
    hub = InstrumentationHub()
    hub.emit_loader_retry(
        loader_name="demo",
        callsite="load",
        attempt_num=1,
        max_attempts=3,
        elapsed_seconds=0.0,
        sleep_seconds=0.0,
        error_type="RuntimeError",
        error_message=None,
    )


def test_hub_emit_lazy_calls_factory_when_wanted() -> None:
    hook = _CaptureSubsetOnEventHook()
    hub = InstrumentationHub()
    hub.register(hook)

    calls = {"n": 0}

    def _factory():  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return PipelineStartEvent(targets=["x"], batch_size=1)

    event = hub.emit_lazy(EventType.PIPELINE_START, _factory)
    assert event is not None
    assert calls["n"] == 1


def test_hub_on_event_receives_catalog_events() -> None:
    hook = _CaptureOnEventHook()
    hub = InstrumentationHub()
    hub.register(hook)

    hub.emit_pipeline_start(targets=["x"], batch_size=1)
    hub.emit_stage_span(stage="compute", batch_num=1, duration=0.01)

    assert [e.event_type for e in hook.events] == [EventType.PIPELINE_START, EventType.STAGE_SPAN]
    assert isinstance(hook.events[0].payload, PipelineStartEvent)
    assert isinstance(hook.events[1].payload, StageSpanEvent)


def test_hub_on_event_supports_subset_subscription_via_event_types() -> None:
    hook = _CaptureSubsetOnEventHook()
    hub = InstrumentationHub()
    hub.register(hook)

    hub.emit_pipeline_start(targets=["x"], batch_size=1)
    hub.emit_pipeline_end(total_batches=0, total_duration=0.0)

    assert [e.event_type for e in hook.events] == [EventType.PIPELINE_START]


def test_hub_on_event_and_typed_callbacks_are_both_invoked() -> None:
    class _DualHook(BaseHook):
        event_types = {EventType.PIPELINE_START}

        def __init__(self) -> None:
            self.on_event_events = []
            self.typed_events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.on_event_events.append(event)

        def on_pipeline_start(self, event: PipelineStartEvent) -> None:  # type: ignore[override]
            self.typed_events.append(event)

    hook = _DualHook()
    hub = InstrumentationHub()
    hub.register(hook)

    hub.emit_pipeline_start(targets=["x"], batch_size=1)

    assert hook.typed_events and isinstance(hook.typed_events[0], PipelineStartEvent)
    assert hook.on_event_events and hook.on_event_events[0].event_type == EventType.PIPELINE_START


def test_base_hook_does_not_enable_typed_subscription_by_default() -> None:
    hooks = HookManager()
    hooks.register(BaseHook())

    assert hooks.wants_typed(EventType.PIPELINE_START) is False
    assert hooks.wants(EventType.PIPELINE_START) is False

    hub = InstrumentationHub(hook_manager=hooks, observer_manager=ObserverManager())
    assert hub.wants(EventType.PIPELINE_START) is False


def test_hub_register_unregister_and_clear_cover_observer_and_hook_paths() -> None:
    hub = InstrumentationHub()

    obs = _CaptureObserver()
    hub.register(obs)
    assert hub.observer_manager.observers
    assert hub.unregister(obs) is True

    hook = _CaptureSubsetOnEventHook()
    hub.register(hook)
    assert hub.hook_manager.hooks
    assert hub.unregister(hook) is True

    hub.register(hook)
    hub.register(obs)
    hub.clear()
    assert hub.hook_manager.hooks == []
    assert hub.observer_manager.observers == []


def test_hub_register_raises_typeerror_on_invalid_component() -> None:
    hub = InstrumentationHub()
    with pytest.raises(TypeError, match=r"Invalid component at index 0"):
        hub.register(object())  # type: ignore[arg-type]


def test_hub_setstate_rebuilds_lock_and_backfills_warning_flag() -> None:
    hub = InstrumentationHub()
    state = hub.__getstate__()
    state.pop("_diagnostic_warning_emitted", None)

    restored = InstrumentationHub.__new__(InstrumentationHub)
    restored.__setstate__(state)
    assert restored._diagnostic_warning_emitted is False  # noqa: SLF001


def test_hub_emit_returns_none_when_unwanted() -> None:
    hub = InstrumentationHub()
    assert hub.emit(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1)) is None


def test_hub_emit_returns_event_when_wanted() -> None:
    hook = _CaptureSubsetOnEventHook()
    hub = InstrumentationHub()
    hub.register(hook)

    payload = PipelineStartEvent(targets=["x"], batch_size=1)
    event = hub.emit(EventType.PIPELINE_START, payload)

    assert event is not None
    assert event.event_type == EventType.PIPELINE_START
    assert hook.events and hook.events[0] is event


def test_hub_typed_helpers_only_check_wants_once() -> None:
    class _CountingHookManager(HookManager):
        def __init__(self) -> None:
            super().__init__()
            self.wants_calls = 0

        def wants(self, event_type: str) -> bool:
            self.wants_calls += 1
            return super().wants(event_type)

    hooks = _CountingHookManager()
    hub = InstrumentationHub(hook_manager=hooks, observer_manager=ObserverManager())
    hub.register(_CaptureSubsetOnEventHook())

    hub.emit_pipeline_start(targets=["x"], batch_size=1)

    assert hooks.wants_calls == 1


def test_hub_emit_loader_call_triggers_typed_hooks_without_building_event() -> None:
    class _TypedLoaderHook(BaseHook):
        def __init__(self) -> None:
            self.calls = []

        def on_loader_call(self, event) -> None:  # type: ignore[override]
            self.calls.append(event)

    hook = _TypedLoaderHook()
    hub = InstrumentationHub()
    hub.register(hook)
    hub.emit_loader_call(loader_name="l", params={}, result={"a": 1}, duration=0.01)
    assert hook.calls


def test_hub_emit_loader_call_on_event_honors_loader_result_policy_variants() -> None:
    hook = _CaptureOnEventHook()
    hook.event_types = {EventType.LOADER_CALL}  # type: ignore[assignment]

    manager_none = ObserverManager(loader_result_policy=LoaderResultPolicy.NONE)
    hub_none = InstrumentationHub(hook_manager=HookManager(), observer_manager=manager_none)
    hub_none.register(hook)
    hub_none.emit_loader_call(loader_name="l", params={}, result={"a": 1}, duration=0.01)
    assert hook.events[-1].payload.result is None

    hook.events = []
    manager_summary = ObserverManager(loader_result_policy=LoaderResultPolicy.SUMMARY)
    hub_summary = InstrumentationHub(hook_manager=HookManager(), observer_manager=manager_summary)
    hub_summary.register(hook)
    hub_summary.emit_loader_call(loader_name="l", params={}, result={"a": 1}, duration=0.01)
    assert hook.events[-1].payload.result["type"] == "dict"

    hook.events = []
    manager_sample = ObserverManager(loader_result_policy=LoaderResultPolicy.SAMPLE, loader_result_sample_size=1)
    hub_sample = InstrumentationHub(hook_manager=HookManager(), observer_manager=manager_sample)
    hub_sample.register(hook)
    hub_sample.emit_loader_call(loader_name="l", params={}, result={"a": 1, "b": 2}, duration=0.01)
    assert hook.events[-1].payload.result == {"a": 1}


def test_hub_emit_diagnostic_warning_falls_back_when_unsubscribed(caplog) -> None:
    hub = InstrumentationHub(
        hook_manager=HookManager(fallback_logger_enabled=False),
        observer_manager=ObserverManager(fallback_logger_enabled=True),
    )
    with caplog.at_level(logging.WARNING, logger="scalim.ob.manager"):
        hub.emit_diagnostic_warning(message="msg", source_id="s", field_id="f", lookup_key=1, row_id=1)

    assert any("诊断" in record.getMessage() for record in caplog.records)


def test_hub_emit_diagnostic_warning_emits_event_when_on_event_hook_present() -> None:
    class _DiagHook(BaseHook):
        event_types = {EventType.DIAGNOSTIC_WARNING}

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    hook = _DiagHook()
    hub = InstrumentationHub()
    hub.register(hook)
    hub.emit_diagnostic_warning(message="msg", source_id="s", field_id="f", lookup_key=1, row_id=1)
    assert hook.events and hook.events[0].event_type == EventType.DIAGNOSTIC_WARNING


def test_hub_emit_loader_slim_emits_when_wanted() -> None:
    class _LoaderSlimHook(BaseHook):
        event_types = {EventType.LOADER_SLIM}

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    hook = _LoaderSlimHook()
    hub = InstrumentationHub()
    hub.register(hook)
    hub.emit_loader_slim(loader_name="l", original_keys=2, extracted_fields=["a"], batch_num=1)
    assert hook.events and hook.events[0].event_type == EventType.LOADER_SLIM


def test_hub_typed_helpers_return_when_unwanted() -> None:
    hub = InstrumentationHub()
    hub.emit_error(RuntimeError("boom"), {"x": 1})
    hub.emit_loader_slim(loader_name="l", original_keys=1, extracted_fields=[], batch_num=1)
    hub.emit_stage_span(stage="compute", batch_num=1, duration=0.0)


def _build_single_compute_plan() -> ExecutionPlan:
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.main_loader"))
    field_a = FieldIr(field_id="a", name="A", source=main_source)
    field_b = FieldIr(field_id="b", name="B", source=main_source)
    derived_sum = DerivedFieldIr(
        field_id="sum",
        name="Sum",
        dependencies=("a", "b"),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.sum"),
            args=(
                CallByValueIr(kind="field", value="a"),
                CallByValueIr(kind="field", value="b"),
            ),
            field_names=("a", "b"),
        ),
    )

    op = ComputeOperatorIr(
        operator_id="compute_sum",
        operator_type=OperatorType.COMPUTE.value,
        field_key="sum",
        input_fields=("a", "b"),
    )

    metadata = PlanMetadata(total_fields=3, total_sources=1, total_loaders=0, has_derived_fields=True)
    stages = [Stage(stage_id="stage0", field_keys=["a", "b", "sum"], level=0)]
    return ExecutionPlan(
        operators=(op,),
        primary_field=None,
        key_fields=frozenset(),
        preload_sources=(),
        field_order=["a", "b", "sum"],
        loader_sequence=[],
        ref_loader_sequence=[],
        stages=stages,
        metadata=metadata,
        field_specs={"a": field_a, "b": field_b, "sum": derived_sum},
        target_fields=["sum"],
        field_dependencies={"sum": ("a", "b")},
    )


def test_stage_span_timing_is_not_performed_when_unsubscribed() -> None:
    plan = _build_single_compute_plan()
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.main_loader"))
    runtime_bindings = RuntimeBindings()
    runtime_bindings.derived_calculators["sum"] = lambda a, b: a + b  # type: ignore[no-any-return]

    observer_manager = ObserverManager(observers=[LoggingObserver(logger=logging.getLogger("test"))], fallback_logger_enabled=False)
    runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(fallback_logger_enabled=False),
        observer_manager=observer_manager,
        main_source=main_source,
        sources={},
        runtime_bindings=runtime_bindings,
    )

    def _explode_perf_counter() -> float:
        raise AssertionError("unexpected stage-span perf_counter call")

    executor = BatchExecutor(plan, runtime, overrides=PipelineOverrides(stage_perf_counter_fn=_explode_perf_counter))

    rows = executor.execute_batch([0], 1, main_rows={0: {"a": 1, "b": 2}})
    assert rows[0]["sum"] == 3


def test_yaml_default_silent_does_not_create_logging_observer() -> None:
    # Observability presets are opt-in: attaching a performance observer should not implicitly attach logging observers.
    observers = (PerformanceObserver(),)
    assert any(isinstance(obs, PerformanceObserver) for obs in observers)
    assert not any(isinstance(obs, LoggingObserver) for obs in observers)
