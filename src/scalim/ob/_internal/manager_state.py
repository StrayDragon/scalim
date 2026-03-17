import contextlib
import threading
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, Deque, Dict, Optional, cast
from typing import Iterable as TypingIterable

from ...events.event import Event
from .common import CAPTURE_OVERFLOW_POLICIES, DEFAULT_MAX_RECORDED_EVENTS


class ObserverManagerStateMixin(ABC):
    max_recorded_events: Optional[int] = None
    capture_overflow_policy: str = "raise"
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
        _ = state_map.setdefault("max_recorded_events", DEFAULT_MAX_RECORDED_EVENTS)
        _ = state_map.setdefault("capture_overflow_policy", "raise")

        max_recorded_events = state_map.get("max_recorded_events")
        self.max_recorded_events = self._normalize_max_recorded_events(max_recorded_events)
        self.capture_overflow_policy = self._normalize_capture_overflow_policy(str(state_map.get("capture_overflow_policy") or "raise"))

        recorded = state_map.get("_recorded_events")
        if recorded is None:
            self._recorded_events = deque()
        elif isinstance(recorded, deque):
            self._recorded_events = recorded
        elif isinstance(recorded, Iterable):
            self._recorded_events = deque(cast("TypingIterable[Event]", recorded))
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

    def _normalize_capture_overflow_policy(self, policy: str) -> str:
        normalized = (policy or "raise").strip().lower().replace("_", "-")
        if normalized not in CAPTURE_OVERFLOW_POLICIES:
            msg = "Unknown capture_overflow_policy: '{}'".format(policy)
            raise ValueError(msg)
        return normalized

    def _normalize_loader_result_policy(self, policy: str) -> str:
        normalized = (policy or "full").lower()
        if normalized not in ("full", "summary", "sample", "none"):
            msg = "Unknown loader_result_policy: '{}'".format(policy)
            raise ValueError(msg)
        return normalized

    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        summary: Dict[str, Any] = {"type": type(result).__name__}
        if isinstance(result, SizedABC):
            with contextlib.suppress(Exception):
                summary["size"] = len(result)
        return summary

    def _sample_result(self, result: Any) -> Any:
        sample: Any = None
        if isinstance(result, MappingABC):
            mapping = cast("MappingABC[Any, Any]", result)
            sample = dict(list(mapping.items())[: self.loader_result_sample_size])
        elif isinstance(result, list):
            items = cast("list[Any]", result)
            sample = items[: self.loader_result_sample_size]
        elif isinstance(result, tuple):
            items = cast("tuple[Any, ...]", result)
            sample = list(items[: self.loader_result_sample_size])
        elif isinstance(result, AbstractSet):
            sample = list(islice(result, self.loader_result_sample_size))
        elif isinstance(result, (str, bytes)):
            sample = result[: self.loader_result_sample_size]
        elif isinstance(result, SequenceABC):
            with contextlib.suppress(Exception):
                sequence = cast("SequenceABC[Any]", result)
                sample = list(sequence[: self.loader_result_sample_size])
        if sample is None:
            return self._summarize_result(result)
        return sample

    def summarize_result(self, result: Any) -> Dict[str, Any]:
        return self._summarize_result(result)

    def sample_result(self, result: Any) -> Any:
        return self._sample_result(result)
