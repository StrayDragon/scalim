import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple, cast

from ..._internal.utils.loader_result import LoaderResultPolicy, LoaderResultPolicyValue, parse_loader_result_policy
from ...events import Event
from ..observer import Observer
from .common import (
    CaptureOverflowPolicy,
    CaptureOverflowPolicyValue,
    ObserverManagerMode,
    ScalimObserverCaptureOverflowError,
    parse_capture_overflow_policy,
    parse_observer_manager_mode,
)


class ObserverManagerCaptureMixin:
    debug_mode: bool = False
    fallback_logger_enabled: bool = False
    loader_result_policy: LoaderResultPolicyValue = "full"
    loader_result_sample_size: int = 5
    run_id: str = ""
    max_recorded_events: Optional[int] = None
    capture_overflow_policy: CaptureOverflowPolicyValue = "raise"
    _lock: "threading.RLock" = threading.RLock()
    _supported_event_types: Optional[Set[str]] = None
    _observers_for_unknown_event_type: Tuple[Observer, ...] = ()
    _capture_event_types: Optional[Set[str]] = None
    _capture_unknown_event_types: bool = False
    _recorded_events: Optional[Deque[Event]] = None
    _event_meta_defaults: Optional[Dict[str, Any]] = None

    def _record_event(self, event: Event) -> None:
        with self._lock:
            recorded_events = self._recorded_events
            if recorded_events is None:
                recorded_events = cast("Deque[Event]", deque())  # pragma: allow-cast deque typed narrowing
                self._recorded_events = recorded_events
            max_recorded_events = self.max_recorded_events
            if max_recorded_events is None:
                recorded_events.append(event)
                return

            limit = int(max_recorded_events)
            if limit <= 0:
                if self.capture_overflow_policy == "raise":
                    msg = (
                        "ObserverManager capture recorded events overflow (limit=0). "
                        "Set max_recorded_events to a positive value, or set capture_overflow_policy to 'drop-oldest'/'drop-newest'."
                    )
                    raise ScalimObserverCaptureOverflowError(msg)
                return

            if len(recorded_events) < limit:
                recorded_events.append(event)
                return

            policy = self.capture_overflow_policy
            if policy == "drop-newest":
                return
            if policy == "drop-oldest":
                _ = recorded_events.popleft()
                recorded_events.append(event)
                return

            msg = (
                "ObserverManager capture recorded events overflow (size={}, limit={}, policy={}). "
                "Increase max_recorded_events, or set capture_overflow_policy to 'drop-oldest'/'drop-newest'."
            ).format(len(recorded_events), limit, policy)
            raise ScalimObserverCaptureOverflowError(msg)

    def drain_events(self) -> List[Event]:
        with self._lock:
            recorded_events = self._recorded_events
            if recorded_events is None:
                recorded_events = cast("Deque[Event]", deque())  # pragma: allow-cast deque typed narrowing
                self._recorded_events = recorded_events
            if not recorded_events:
                return []
            events = list(recorded_events)
            recorded_events.clear()
            return events

    def create_capture_manager(self) -> Any:
        manager_cls = cast("Any", type(self))  # pragma: allow-cast manager class boundary typed narrowing
        loader_result_policy_value = parse_loader_result_policy(self.loader_result_policy)
        capture_overflow_policy_value = parse_capture_overflow_policy(self.capture_overflow_policy)
        mode_value = parse_observer_manager_mode("capture")
        capture = manager_cls(
            observers=None,
            enable_debugging=self.debug_mode,
            fallback_logger_enabled=self.fallback_logger_enabled,
            loader_result_policy=LoaderResultPolicy(loader_result_policy_value),
            loader_result_sample_size=self.loader_result_sample_size,
            run_id=self.run_id,
            event_meta_defaults=self._event_meta_defaults,
            mode=ObserverManagerMode(mode_value),
            max_recorded_events=self.max_recorded_events,
            capture_overflow_policy=CaptureOverflowPolicy(capture_overflow_policy_value),
        )
        capture._capture_event_types = set(self._supported_event_types or ())  # noqa: SLF001
        capture._capture_unknown_event_types = bool(self._observers_for_unknown_event_type)  # noqa: SLF001
        return capture


__all__ = ()
