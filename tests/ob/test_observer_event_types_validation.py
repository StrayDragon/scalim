import pytest

from scalim.events import EventType, parse_event_type
from scalim.ob._internal.common import ObserverManagerMode, validate_event_types
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver


def test_validate_event_types_rejects_bare_str() -> None:
    class _Observer:
        pass

    observer = _Observer()
    with pytest.raises(TypeError, match=r"contain only EventType"):
        validate_event_types(observer, {"unknown-event-type"})


def test_validate_event_types_rejects_non_event_type_element() -> None:
    class _Observer:
        pass

    with pytest.raises(TypeError, match=r"contain only EventType"):
        validate_event_types(_Observer(), {123})


def test_validate_event_types_rejects_policy_signal_not_in_observer_catalog() -> None:
    class _Observer:
        pass

    with pytest.raises(ValueError, match=r"unknown event type"):
        validate_event_types(_Observer(), {EventType.PRE_USE_BATCH_SIZE})


def test_parse_event_type_rejects_unknown_string() -> None:
    with pytest.raises(ValueError, match=r"unknown event_type"):
        parse_event_type("not-a-real-event")


def test_parse_event_type_rejects_non_str_non_enum() -> None:
    with pytest.raises(TypeError, match=r"EventType or builtin str"):
        parse_event_type(123)


def test_coerce_event_type_accepts_builtin_str_value() -> None:
    from scalim.workflow.execute_controller import _coerce_event_type

    assert _coerce_event_type(EventType.PIPELINE_START.value) is EventType.PIPELINE_START
    assert _coerce_event_type(EventType.PIPELINE_START) is EventType.PIPELINE_START


def test_infer_dispatch_skips_event_type_outside_observer_catalog() -> None:
    class _Obs(EventDispatchObserver):
        dispatch_map = {EventType.PRE_USE_BATCH_SIZE: "on_pre_use_batch_size"}

        def on_pre_use_batch_size(self, event: object) -> None:
            _ = event

    manager = ObserverManager()
    manager.register(_Obs())
    assert manager.wants(EventType.PRE_USE_BATCH_SIZE) is False


def test_normalize_recorded_events_skips_non_event_objects() -> None:
    from scalim.events import Event, PipelineStartEvent

    manager = ObserverManager(mode=ObserverManagerMode.CAPTURE)
    normalized = manager._normalize_recorded_events(  # noqa: SLF001
        [
            "not-an-event",
            object(),
            Event(
                event_type=EventType.PIPELINE_START,
                timestamp=0.0,
                run_id="r",
                payload=PipelineStartEvent(targets=[], batch_size=None),
            ),
        ]
    )
    assert len(list(normalized)) == 1
