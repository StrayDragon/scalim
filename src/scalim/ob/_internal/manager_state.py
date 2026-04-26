import threading
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable
from typing import Any, Deque, Dict, Optional, cast
from typing import Iterable as TypingIterable

from ..._internal.utils.loader_result import (
    LoaderResultPolicy,
    LoaderResultPolicyLike,
    normalize_loader_result_policy,
    sample_loader_result,
    summarize_loader_result,
)
from ...events import Event
from .common import (
    CAPTURE_OVERFLOW_POLICIES,
    DEFAULT_MAX_RECORDED_EVENTS,
    CaptureOverflowPolicy,
    ObserverManagerMode,
    normalize_observer_manager_mode,
)


class ObserverManagerStateMixin(ABC):
    mode: ObserverManagerMode = ObserverManagerMode.PROCESS
    max_recorded_events: Optional[int] = None
    capture_overflow_policy: CaptureOverflowPolicy = CaptureOverflowPolicy.RAISE
    loader_result_sample_size: int = 5
    _lock: "threading.RLock" = threading.RLock()
    _recorded_events: Optional[Deque[Event]] = None

    @abstractmethod
    def _rebuild_subscription_cache(self) -> None: ...

    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        state.pop("_observers_by_event_type", None)
        state.pop("_observers_for_unknown_event_type", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        state_map = vars(self)
        state_map.update(state)
        self._lock = threading.RLock()
        _ = state_map.setdefault("_has_observers", bool(state_map.get("observers", [])))
        _ = state_map.setdefault("_supports_all", False)
        _ = state_map.setdefault("_supported_event_types", set())
        _ = state_map.setdefault("_observers_by_event_type", {})
        _ = state_map.setdefault("_observers_for_unknown_event_type", ())
        _ = state_map.setdefault("_capture_event_types", None)
        _ = state_map.setdefault("_capture_unknown_event_types", False)
        _ = state_map.setdefault("_event_meta_defaults", None)
        _ = state_map.setdefault("mode", "process")
        _ = state_map.setdefault("max_recorded_events", DEFAULT_MAX_RECORDED_EVENTS)
        _ = state_map.setdefault("capture_overflow_policy", "raise")

        self.mode = self._normalize_mode(state_map.get("mode"))
        max_recorded_events = state_map.get("max_recorded_events")
        self.max_recorded_events = self._normalize_max_recorded_events(max_recorded_events)
        self.capture_overflow_policy = self._normalize_capture_overflow_policy(state_map.get("capture_overflow_policy") or "raise")

        recorded = state_map.get("_recorded_events")
        if recorded is None:
            self._recorded_events = deque()
        elif isinstance(recorded, deque):
            self._recorded_events = recorded
        elif isinstance(recorded, Iterable):
            self._recorded_events = deque(cast("TypingIterable[Event]", recorded))  # pragma: allow-cast iterable typed narrowing
        else:
            self._recorded_events = deque()
        self._rebuild_subscription_cache()

    def _normalize_max_recorded_events(self, max_recorded_events: Optional[int]) -> Optional[int]:
        if max_recorded_events is None:
            return None
        resolved = int(max_recorded_events)
        if resolved < 0:
            msg = "max_recorded_events must be >= 0 or None"
            raise ValueError(msg)
        return resolved

    def _normalize_capture_overflow_policy(self, policy: object) -> CaptureOverflowPolicy:
        if isinstance(policy, CaptureOverflowPolicy):
            return policy
        if not isinstance(policy, str):
            msg = "capture_overflow_policy must be a str, got '{}'".format(type(policy).__name__)
            raise TypeError(msg)
        normalized = (policy or "raise").strip().lower().replace("_", "-")
        if normalized not in CAPTURE_OVERFLOW_POLICIES:
            msg = "Unknown capture_overflow_policy: '{}'".format(policy)
            raise ValueError(msg)
        return CaptureOverflowPolicy(normalized)

    def _normalize_mode(self, value: object) -> ObserverManagerMode:
        return normalize_observer_manager_mode(value)

    def _normalize_loader_result_policy(self, policy: LoaderResultPolicyLike) -> LoaderResultPolicy:
        return normalize_loader_result_policy(policy)

    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        return summarize_loader_result(result)

    def _sample_result(self, result: Any) -> Any:
        return sample_loader_result(result, sample_size=self.loader_result_sample_size)

    def summarize_result(self, result: Any) -> Dict[str, Any]:
        return summarize_loader_result(result)

    def sample_result(self, result: Any) -> Any:
        return sample_loader_result(result, sample_size=self.loader_result_sample_size)


__all__ = ()
