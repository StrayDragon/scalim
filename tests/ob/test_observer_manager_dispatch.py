import pytest

from scalim.events import Event, EventType
from scalim.events._events import PipelineStartEvent
from scalim.ob._internal.common import ObserverManagerMode
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver, Observer


def test_observer_supports_respects_event_types() -> None:
    class _Obs(Observer):
        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    obs = _Obs()
    assert obs.supports("x") is True

    obs.event_types = {"y"}  # type: ignore[assignment]
    assert obs.supports("x") is False
    assert obs.supports("y") is True


class _BadDispatchObserver(EventDispatchObserver):
    dispatch_map = None  # type: ignore[assignment]

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        _ = event


def test_observer_manager_infers_no_subscriptions_when_dispatch_map_is_not_dict() -> None:
    manager = ObserverManager(observers=[_BadDispatchObserver()])
    assert manager.wants(EventType.PIPELINE_START) is False


class _NonCatalogDispatchObserver(EventDispatchObserver):
    dispatch_map = {"non_catalog": "on_pipeline_start", EventType.PIPELINE_START: "on_pipeline_start"}

    def __init__(self) -> None:
        self.events = []

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        self.events.append(event)


def test_observer_manager_inference_skips_non_catalog_event_types_in_dispatch_map() -> None:
    obs = _NonCatalogDispatchObserver()
    manager = ObserverManager(observers=[obs])
    manager.emit_event(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1))
    assert obs.events


class _CustomSupportsObserver(Observer):
    def supports(self, event_type: str) -> bool:
        return event_type == str(EventType.PIPELINE_START)

    def __init__(self) -> None:
        self.events = []

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_observer_manager_infers_subscriptions_via_custom_supports() -> None:
    manager = ObserverManager(observers=[_CustomSupportsObserver()])
    assert manager.wants(EventType.PIPELINE_START) is True
    assert manager.wants(EventType.PIPELINE_END) is False


def test_observer_manager_does_not_dispatch_unknown_event_types_without_explicit_opt_in() -> None:
    class _SupportsAllCustomObserver(Observer):
        def supports(self, event_type: str) -> bool:
            return True

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    obs = _SupportsAllCustomObserver()
    manager = ObserverManager(observers=[obs])
    manager.emit_event("unknown", payload=None)

    assert obs.events == []


def test_observer_manager_dispatches_unknown_event_types_with_explicit_opt_in() -> None:
    class _SupportsAllCustomObserver(Observer):
        supports_unknown_event_types = True

        def supports(self, event_type: str) -> bool:
            return True

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    obs = _SupportsAllCustomObserver()
    manager = ObserverManager(observers=[obs])
    manager.emit_event("unknown", payload=None)

    assert len(obs.events) == 1
    assert obs.events[0].event_type == "unknown"


class _CaptureAllObserver(Observer):
    def __init__(self) -> None:
        self.events = []

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_observer_manager_typed_emit_helpers_cover_all_event_types() -> None:
    obs = _CaptureAllObserver()
    manager = ObserverManager(observers=[obs])

    manager.emit_pipeline_end(total_batches=1, total_duration=0.1)
    manager.emit_batch_start(batch_num=1, row_ids=[1])
    manager.emit_batch_end(batch_num=1, duration=0.2)
    manager.emit_loader_retry(
        loader_name="demo",
        callsite="load",
        attempt_num=1,
        max_attempts=3,
        elapsed_seconds=0.0,
        sleep_seconds=0.0,
        error_type="RuntimeError",
        error_message=None,
        batch_num=1,
    )
    manager.emit_field_compute(field_key="f", row_id=1, dependencies={}, result=1)
    manager.emit_field_slim(field_key="f", reason="x", batch_num=1, remaining_fields=0)
    manager.emit_row_write(row_id=1, field_count=1, batch_num=1, row_index=0)
    manager.emit_row_release(row_id=1, released_fields=[], retained_fields=[], batch_num=1)
    manager.emit_relation_lookup(
        field_key="f",
        row_id=1,
        fk_raw=1,
        fk_normalized=1,
        target_source="s",
        result="hit",
    )
    manager.emit_stage_span(stage="compute", batch_num=1, duration=0.01)

    emitted = [e.event_type for e in obs.events]
    assert EventType.BATCH_START in emitted
    assert EventType.BATCH_END in emitted
    assert EventType.LOADER_RETRY in emitted


def test_observer_manager_typed_emit_helpers_return_when_unwanted() -> None:
    manager = ObserverManager()
    manager.emit_error(RuntimeError("boom"), {"x": 1})
    manager.emit_loader_retry(
        loader_name="demo",
        callsite="load",
        attempt_num=1,
        max_attempts=3,
        elapsed_seconds=0.0,
        sleep_seconds=0.0,
        error_type="RuntimeError",
        error_message=None,
        batch_num=1,
    )
    manager.emit_loader_slim(loader_name="l", original_keys=1, extracted_fields=[], batch_num=1)
    manager.emit_column_write(field_key="f", row_count=1, batch_num=1)


def test_observer_manager_typed_emit_helpers_return_when_unsubscribed() -> None:
    class _PipelineStartOnlyObserver(Observer):
        event_types = {EventType.PIPELINE_START}

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    manager = ObserverManager(observers=[_PipelineStartOnlyObserver()])

    manager.emit_batch_start(batch_num=1, row_ids=[1])
    manager.emit_batch_end(batch_num=1, duration=0.0)
    manager.emit_field_compute(field_key="f", row_id=1, dependencies={}, result=1)
    manager.emit_field_slim(field_key="f", reason="x", batch_num=1, remaining_fields=0)
    manager.emit_row_write(row_id=1, field_count=1, batch_num=1, row_index=0)
    manager.emit_row_release(row_id=1, released_fields=[], retained_fields=[], batch_num=1)
    manager.emit_relation_lookup(
        field_key="f",
        row_id=1,
        fk_raw=1,
        fk_normalized=1,
        target_source="s",
        result="hit",
    )
    manager.emit_stage_span(stage="compute", batch_num=1, duration=0.0)


def test_observer_manager_register_rejects_invalid_event_types_type() -> None:
    class _InvalidEventTypesObserver(Observer):
        event_types = ["x"]  # type: ignore[assignment]

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    manager = ObserverManager()
    with pytest.raises(TypeError, match="event_types"):
        manager.register(_InvalidEventTypesObserver())


def test_observer_manager_register_rejects_event_types_with_non_str_entries() -> None:
    class _InvalidEventTypesObserver(Observer):
        event_types = {EventType.PIPELINE_START, 123}  # type: ignore[assignment]

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    manager = ObserverManager()
    with pytest.raises(TypeError, match="contain only str"):
        manager.register(_InvalidEventTypesObserver())


def test_observer_manager_setstate_backfills_capture_unknown_event_types() -> None:
    manager = ObserverManager()
    state = manager.__getstate__()
    state.pop("_capture_unknown_event_types", None)

    restored = ObserverManager.__new__(ObserverManager)
    restored.__setstate__(state)

    assert restored._capture_unknown_event_types is False  # noqa: SLF001


def test_observer_manager_wants_unknown_event_type_in_capture_mode_respects_flag() -> None:
    manager = ObserverManager(mode=ObserverManagerMode.CAPTURE)
    assert manager.wants("unknown") is False

    manager._capture_unknown_event_types = True  # noqa: SLF001
    assert manager.wants("unknown") is True


def test_observer_manager_wants_unknown_event_type_is_false_without_observers() -> None:
    manager = ObserverManager()
    assert manager.wants("unknown") is False


def test_observer_manager_wants_unknown_event_type_is_true_with_opt_in_observer() -> None:
    class _UnknownObserver(Observer):
        supports_unknown_event_types = True

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    manager = ObserverManager(observers=[_UnknownObserver()])
    assert manager.wants("unknown") is True


def test_observer_manager_emit_unknown_event_skips_observer_when_supports_returns_false() -> None:
    class _SkipUnknownObserver(Observer):
        supports_unknown_event_types = True
        event_types = {EventType.PIPELINE_START}

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    class _AcceptUnknownObserver(Observer):
        supports_unknown_event_types = True

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    skip = _SkipUnknownObserver()
    accept = _AcceptUnknownObserver()
    manager = ObserverManager(observers=[skip, accept])
    manager.emit_event("unknown", payload=None)

    assert skip.events == []
    assert len(accept.events) == 1
    assert accept.events[0].event_type == "unknown"


def test_observer_manager_emit_returns_when_subscription_tuple_is_empty() -> None:
    manager = ObserverManager()
    manager._has_observers = True  # noqa: SLF001
    manager._observers_by_event_type = {EventType.PIPELINE_START: ()}  # noqa: SLF001

    manager.emit_event(EventType.PIPELINE_START, PipelineStartEvent(targets=["x"], batch_size=1))
