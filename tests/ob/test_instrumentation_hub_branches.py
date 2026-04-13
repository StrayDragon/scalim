from typing import Any, Dict, List, Optional

from scalim.events import Event
from scalim.ob.hub import InstrumentationHub


def test_instrumentation_hub_emit_recorded_event_capture_skips_hook_on_event() -> None:
    class _HookManagerStub:
        def __init__(self) -> None:
            self.calls: List[object] = []

        def emit_on_event(self, event: object) -> None:  # type: ignore[no-untyped-def]
            self.calls.append(event)

    class _ObserverManagerStub:
        def __init__(self) -> None:
            self.mode = "capture"
            self.emitted: List[object] = []

        def emit(self, event: object) -> None:  # type: ignore[no-untyped-def]
            self.emitted.append(event)

    hook_manager = _HookManagerStub()
    observer_manager = _ObserverManagerStub()
    hub = InstrumentationHub(hook_manager=hook_manager, observer_manager=observer_manager)  # type: ignore[arg-type]

    event = Event(event_type="demo", timestamp=0.0, run_id="run", payload=None)
    hub.emit_recorded_event(event)

    assert observer_manager.emitted == [event]
    assert hook_manager.calls == []


def test_instrumentation_hub_emit_diagnostic_warning_returns_when_unwanted_and_no_fallback() -> None:
    hub = InstrumentationHub()

    def _forbid_emit_diagnostic_warning(**_kwargs: object) -> None:
        raise AssertionError("should not emit diagnostic warning without subscribers or fallback logger")

    hub.observer_manager.emit_diagnostic_warning = _forbid_emit_diagnostic_warning  # type: ignore[method-assign]

    hub.emit_diagnostic_warning(
        message="hello",
        source_id="src",
        field_id="field",
        lookup_key="k",
        row_id=1,
        sample_once=False,
    )


def test_instrumentation_hub_emit_diagnostic_warning_capture_mode_skips_hook_on_event() -> None:
    class _HookManagerStub:
        fallback_logger_enabled = False

        def __init__(self) -> None:
            self.on_event_calls: List[object] = []

        def wants_typed(self, _event_type: str) -> bool:
            return False

        def wants_on_event(self, _event_type: str) -> bool:
            return True

        def emit_typed(self, _event_type: str, _payload: object) -> None:
            return None

        def emit_on_event(self, event: object) -> None:  # type: ignore[no-untyped-def]
            self.on_event_calls.append(event)

    class _ObserverManagerStub:
        fallback_logger_enabled = False
        mode = "capture"

        def wants(self, _event_type: str) -> bool:
            return False

        def emit_event(self, event_type: str, payload: object, *, meta: Optional[Dict[str, Any]] = None) -> Event:
            return Event(event_type=event_type, timestamp=0.0, run_id="run", payload=payload, meta=meta or {}, seq=1)

    hook_manager = _HookManagerStub()
    observer_manager = _ObserverManagerStub()
    hub = InstrumentationHub(hook_manager=hook_manager, observer_manager=observer_manager)  # type: ignore[arg-type]

    hub.emit_diagnostic_warning(
        message="warn",
        source_id="src",
        field_id="field",
        lookup_key="k",
        row_id=1,
    )

    assert hook_manager.on_event_calls == []


def test_instrumentation_hub_emit_loader_call_unknown_policy_keeps_payload() -> None:
    class _HookManagerStub:
        fallback_logger_enabled = False

        def wants_typed(self, _event_type: str) -> bool:
            return False

        def wants_on_event(self, _event_type: str) -> bool:
            return True

        def emit_on_event(self, _event: object) -> None:
            return None

    class _ObserverManagerStub:
        fallback_logger_enabled = False
        loader_result_policy = "weird"
        mode = "capture"

        def __init__(self) -> None:
            self.payloads: List[object] = []

        def wants(self, _event_type: str) -> bool:
            return False

        def emit_event(self, event_type: str, payload: object, *, meta: Optional[Dict[str, Any]] = None) -> Event:
            self.payloads.append(payload)
            return Event(event_type=event_type, timestamp=0.0, run_id="run", payload=payload, meta=meta or {}, seq=1)

    hook_manager = _HookManagerStub()
    observer_manager = _ObserverManagerStub()
    hub = InstrumentationHub(hook_manager=hook_manager, observer_manager=observer_manager)  # type: ignore[arg-type]

    result = {"k": 1}
    hub.emit_loader_call(
        loader_name="src",
        params={},
        result=result,
        duration=0.1,
        batch_num=1,
    )

    assert observer_manager.payloads
    assert observer_manager.payloads[0].result is result  # type: ignore[attr-defined]
