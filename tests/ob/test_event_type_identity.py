import pytest

from scalim.events import Event, EventType, PipelineStartEvent, parse_event_type
from scalim.hooks import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer


def test_observer_register_rejects_bare_str_event_types() -> None:
    class _BadObserver(Observer):
        event_types = {"pipeline.start"}  # type: ignore[assignment]

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    with pytest.raises(TypeError, match="contain only EventType"):
        ObserverManager().register(_BadObserver())


def test_observer_register_accepts_event_type_set() -> None:
    class _GoodObserver(Observer):
        event_types = {EventType.PIPELINE_START}

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    manager = ObserverManager()
    manager.register(_GoodObserver())
    assert manager.wants(EventType.PIPELINE_START) is True
    assert manager.wants(EventType.PIPELINE_END) is False


def test_hook_register_rejects_bare_str_event_types() -> None:
    class _BadHook(BaseHook):
        event_types = {"pipeline.start"}  # type: ignore[assignment]

    with pytest.raises(TypeError, match="contain only EventType"):
        HookManager().register(_BadHook())


def test_hook_register_accepts_event_type_set() -> None:
    class _GoodHook(BaseHook):
        event_types = {EventType.PIPELINE_START}

        def on_pipeline_start(self, event: Event) -> None:  # type: ignore[override]
            _ = event

    manager = HookManager()
    manager.register(_GoodHook())
    assert manager.wants(EventType.PIPELINE_START) is True


def test_public_payload_import_from_scalim_events() -> None:
    payload = PipelineStartEvent(targets=["a"], batch_size=1)
    assert payload.targets == ["a"]
    assert payload.batch_size == 1


def test_event_to_dict_emits_builtin_str_and_parse_event_type_roundtrip() -> None:
    event = Event(
        event_type=EventType.PIPELINE_START,
        timestamp=0.0,
        run_id="r",
        payload=PipelineStartEvent(targets=["a"], batch_size=1),
        meta={},
        seq=1,
    )
    wire = event.to_dict()
    assert type(wire["event_type"]) is str
    assert wire["event_type"] == EventType.PIPELINE_START.value
    assert parse_event_type(wire["event_type"]) is EventType.PIPELINE_START
