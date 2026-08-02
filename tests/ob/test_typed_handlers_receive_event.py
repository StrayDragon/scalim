"""c35: typed Observer/Hook handlers receive Event (incl. meta.scalim_compute_phase)."""

from typing import List

from scalim.events import Event, EventType, FieldComputeEvent
from scalim.hooks import BaseHook, HookManager
from scalim.ob.hub import InstrumentationHub
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver


class _TypedFieldComputeObserver(EventDispatchObserver):
    def __init__(self) -> None:
        self.events: List[Event] = []

    def on_field_compute(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)


class _TypedFieldComputeHook(BaseHook):
    def __init__(self) -> None:
        self.events: List[Event] = []
        self.on_event_seen: List[Event] = []

    def on_field_compute(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        if event.event_type == EventType.FIELD_COMPUTE:
            self.on_event_seen.append(event)


def test_typed_observer_receives_event_envelope_with_compute_phase_meta() -> None:
    observer = _TypedFieldComputeObserver()
    hub = InstrumentationHub(observer_manager=ObserverManager([observer]), hook_manager=HookManager())

    hub.emit_field_compute(
        field_key="profit",
        row_id=1,
        dependencies={"a": 1},
        result=10,
        meta={"scalim_compute_phase": "write_precompute"},
    )

    assert len(observer.events) == 1
    event = observer.events[0]
    assert isinstance(event, Event)
    assert event.meta.get("scalim_compute_phase") == "write_precompute"
    assert isinstance(event.payload, FieldComputeEvent)
    assert event.payload.field_key == "profit"
    assert event.payload.result == 10


def test_typed_hook_receives_event_envelope_with_compute_phase_meta() -> None:
    hook = _TypedFieldComputeHook()
    manager = HookManager()
    manager.register(hook)

    manager.trigger_field_compute(
        field_key="profit",
        row_id=1,
        dependencies={"a": 1},
        result=10,
        meta={"scalim_compute_phase": "operator"},
    )

    assert len(hook.events) == 1
    event = hook.events[0]
    assert isinstance(event, Event)
    assert event.meta.get("scalim_compute_phase") == "operator"
    assert isinstance(event.payload, FieldComputeEvent)
    assert event.payload.field_key == "profit"


def test_typed_and_on_event_both_see_same_compute_phase_meta() -> None:
    hook = _TypedFieldComputeHook()
    hub = InstrumentationHub(observer_manager=ObserverManager([]), hook_manager=HookManager())
    hub.hook_manager.register(hook)

    hub.emit_field_compute(
        field_key="profit",
        row_id=2,
        dependencies={},
        result=None,
        meta={"scalim_compute_phase": "write_precompute"},
    )

    assert len(hook.events) == 1
    assert len(hook.on_event_seen) == 1
    typed_meta = hook.events[0].meta.get("scalim_compute_phase")
    on_event_meta = hook.on_event_seen[0].meta.get("scalim_compute_phase")
    assert typed_meta == "write_precompute"
    assert on_event_meta == typed_meta
    assert isinstance(hook.events[0].payload, FieldComputeEvent)
