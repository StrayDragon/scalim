from __future__ import annotations

import threading
from typing import Optional, Set

from scalim.events.catalog import (
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_ERROR,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_LOADER_SLIM,
)
from scalim.ob.hub import InstrumentationHub
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.hooks.base import BaseHook, HookManager


class _CaptureObserver(Observer):
    def __init__(self, event_types: Optional[Set[str]] = None) -> None:
        self.event_types = event_types
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def test_hub_getstate_setstate_backfills_lock_and_diagnostic_once_flag() -> None:
    hub = InstrumentationHub()
    state = hub.__getstate__()
    assert "_lock" not in state

    legacy_state = dict(state)
    legacy_state.pop("_diagnostic_warning_emitted", None)

    legacy = InstrumentationHub.__new__(InstrumentationHub)
    legacy.__setstate__(legacy_state)

    assert isinstance(legacy._lock, type(threading.RLock()))  # noqa: SLF001
    assert legacy._diagnostic_warning_emitted is False  # noqa: SLF001


def test_hub_register_unregister_clear_and_emit_gating() -> None:
    observer = _CaptureObserver(event_types={EVENT_ERROR})
    hook = BaseHook()

    hub = InstrumentationHub()
    hub.register(observer)
    hub.register(hook)

    assert hub.wants(EVENT_ERROR) is True
    assert hub.unregister(observer) is True
    assert hub.unregister(hook) is True

    hub.clear()

    called = False

    def payload_factory():  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        return {"x": 1}

    assert hub.emit_lazy(EVENT_ERROR, payload_factory) is None
    assert called is False
    assert hub.emit(EVENT_ERROR, {"x": 1}) is None

    # typed helpers should early-return without subscribers
    hub.emit_field_compute("f", 1, {}, 1)
    hub.emit_stage_span("stage", batch_num=1, duration=0.0)
    hub.emit_loader_slim(loader_name="loader", original_keys=1, extracted_fields=[], batch_num=1)
    hub.emit_loader_retry(
        loader_name="loader",
        callsite="load",
        attempt_num=1,
        max_attempts=3,
        elapsed_seconds=0.1,
        sleep_seconds=0.0,
        error_type="RuntimeError",
        error_message="boom",
        batch_num=1,
    )


def test_hub_emit_error_emits_when_subscribed() -> None:
    observer = _CaptureObserver(event_types={EVENT_ERROR})
    hub = InstrumentationHub(observer_manager=ObserverManager(observers=[observer]))

    hub.emit_error(RuntimeError("boom"), {"x": 1})
    assert observer.events
    assert observer.events[-1].event_type == EVENT_ERROR


def test_hub_emit_returns_event_when_subscribed() -> None:
    observer = _CaptureObserver(event_types={EVENT_ERROR})
    hub = InstrumentationHub(observer_manager=ObserverManager(observers=[observer]))

    event = hub.emit(EVENT_ERROR, {"x": 1})
    assert event is not None
    assert event.event_type == EVENT_ERROR


def test_hub_emit_loader_call_result_policies_cover_sampling_and_wrappers() -> None:
    observer = _CaptureObserver(event_types={EVENT_LOADER_CALL})

    hub_none = InstrumentationHub(observer_manager=ObserverManager(observers=[observer], loader_result_policy="none"))
    hub_none.emit_loader_call("loader", {}, [1, 2, 3], 0.1)

    hub_summary = InstrumentationHub(observer_manager=ObserverManager(observers=[observer], loader_result_policy="summary"))
    hub_summary.emit_loader_call("loader", {}, [1, 2, 3], 0.1)

    hub_sample = InstrumentationHub(
        observer_manager=ObserverManager(observers=[observer], loader_result_policy="sample", loader_result_sample_size=1)
    )
    hub_sample.emit_loader_call("loader", {}, [1, 2, 3], 0.1)

    assert any(evt.event_type == EVENT_LOADER_CALL for evt in observer.events)


def test_hub_emit_diagnostic_warning_fallback_logger_path_and_event_path() -> None:
    hub_fallback = InstrumentationHub(
        hook_manager=HookManager(fallback_logger_enabled=True),
        observer_manager=ObserverManager(fallback_logger_enabled=True),
    )
    hub_fallback.emit_diagnostic_warning(
        message="warn",
        source_id="s",
        field_id="f",
        lookup_key="k",
        row_id=1,
        sample_once=False,
    )

    observer = _CaptureObserver(event_types={EVENT_DIAGNOSTIC_WARNING})
    hub_event = InstrumentationHub(observer_manager=ObserverManager(observers=[observer]))
    hub_event.emit_diagnostic_warning(
        message="warn",
        source_id="s",
        field_id="f",
        lookup_key="k",
        row_id=1,
        sample_once=False,
    )

    assert observer.events
    assert observer.events[-1].event_type == EVENT_DIAGNOSTIC_WARNING


def test_hub_emit_loader_slim_return_and_emit_paths() -> None:
    hub = InstrumentationHub()
    hub.emit_loader_slim(loader_name="loader", original_keys=1, extracted_fields=[], batch_num=1)

    observer = _CaptureObserver(event_types={EVENT_LOADER_SLIM})
    hub2 = InstrumentationHub(observer_manager=ObserverManager(observers=[observer]))
    hub2.emit_loader_slim(loader_name="loader", original_keys=1, extracted_fields=[], batch_num=1)
    assert observer.events


def test_hub_emit_loader_retry_return_and_emit_paths() -> None:
    hub = InstrumentationHub()
    hub.emit_loader_retry(
        loader_name="loader",
        callsite="load",
        attempt_num=1,
        max_attempts=3,
        elapsed_seconds=0.1,
        sleep_seconds=0.0,
        error_type="RuntimeError",
        error_message="boom",
        batch_num=1,
    )

    observer = _CaptureObserver(event_types={EVENT_LOADER_RETRY})
    hub2 = InstrumentationHub(observer_manager=ObserverManager(observers=[observer]))
    hub2.emit_loader_retry(
        loader_name="loader",
        callsite="load",
        attempt_num=1,
        max_attempts=3,
        elapsed_seconds=0.1,
        sleep_seconds=0.0,
        error_type="RuntimeError",
        error_message="boom",
        batch_num=1,
    )
    assert observer.events
    assert observer.events[-1].event_type == EVENT_LOADER_RETRY
