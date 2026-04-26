# region imports

import logging
import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from .._internal.utils.loader_result import LoaderResultPolicy, LoaderResultPolicyLike
from ..events import Event, generate_run_id
from ._internal.common import (
    DEFAULT_MAX_RECORDED_EVENTS,
    CaptureOverflowPolicy,
    CaptureOverflowPolicyLike,
    ObserverManagerMode,
    ObserverManagerModeLike,
    ScalimObserverCaptureOverflowError,
)
from ._internal.common import (
    OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING as _OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING,
)
from ._internal.common import (
    OBSERVER_RAISED_EXCEPTION_WARNING as _OBSERVER_RAISED_EXCEPTION_WARNING,
)
from ._internal.manager_capture import ObserverManagerCaptureMixin
from ._internal.manager_emit import ObserverManagerEmitMixin
from ._internal.manager_registry import ObserverManagerRegistryMixin
from ._internal.manager_state import ObserverManagerStateMixin
from .observer import Observer

# endregion

_logger = logging.getLogger(__name__)

OBSERVER_RAISED_EXCEPTION_WARNING = _OBSERVER_RAISED_EXCEPTION_WARNING
OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING = _OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING


class ObserverManager(
    ObserverManagerRegistryMixin,
    ObserverManagerStateMixin,
    ObserverManagerCaptureMixin,
    ObserverManagerEmitMixin,
):
    """`Observer` 管理器:注册观察者并分发事件.

    注意:请通过 `register`/`unregister`/`clear` 管理观察者;直接修改 `observers` 列表可能导致订阅缓存不同步.
    """

    observers: Optional[List[Observer]]
    _has_observers: bool
    _supports_all: bool
    _supported_event_types: Optional[Set[str]]
    _observers_by_event_type: Optional[Dict[str, Tuple[Observer, ...]]]
    _observers_for_unknown_event_type: Tuple[Observer, ...]
    _capture_event_types: Optional[Set[str]]
    _capture_unknown_event_types: bool
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: LoaderResultPolicy
    loader_result_sample_size: int
    run_id: str
    _event_meta_defaults: Optional[Dict[str, Any]]
    mode: ObserverManagerMode
    max_recorded_events: Optional[int]
    capture_overflow_policy: CaptureOverflowPolicy
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool
    _seq: int
    _recorded_events: Optional[Deque[Event]]

    def __init__(
        self,
        observers: Optional[List[Observer]] = None,
        *,
        enable_debugging: bool = False,
        fallback_logger_enabled: bool = False,
        loader_result_policy: LoaderResultPolicyLike = "full",
        loader_result_sample_size: int = 5,
        run_id: Optional[str] = None,
        event_meta_defaults: Optional[Dict[str, Any]] = None,
        mode: ObserverManagerModeLike = "process",
        max_recorded_events: Optional[int] = DEFAULT_MAX_RECORDED_EVENTS,
        capture_overflow_policy: CaptureOverflowPolicyLike = "raise",
    ) -> None:
        self.observers = list(observers or [])
        self._has_observers = False
        self._supports_all = False
        self._supported_event_types = set()
        self._observers_by_event_type = {}
        self._observers_for_unknown_event_type = ()
        self._capture_event_types = None
        self._capture_unknown_event_types = False
        self.debug_mode = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = self._normalize_loader_result_policy(loader_result_policy)
        self.loader_result_sample_size = max(1, loader_result_sample_size)
        self.run_id = run_id or generate_run_id()
        self._event_meta_defaults = dict(event_meta_defaults) if event_meta_defaults else None
        self.mode = self._normalize_mode(mode)
        self.max_recorded_events = self._normalize_max_recorded_events(max_recorded_events)
        self.capture_overflow_policy = self._normalize_capture_overflow_policy(capture_overflow_policy)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False
        self._seq = 0
        self._recorded_events = deque()
        self._rebuild_subscription_cache()


__all__ = (
    "ObserverManager",
    "ScalimObserverCaptureOverflowError",
)
