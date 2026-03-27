import threading
from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple, cast

from ...events import Event
from ..observer import EventDispatchObserver, Observer
from .common import CATALOG_EVENT_TYPES, CATALOG_EVENT_TYPES_SET, validate_event_types


class ObserverManagerRegistryMixin:
    observers: Optional[List[Observer]] = None
    mode: str = "process"
    _has_observers: bool = False
    _supports_all: bool = False
    _supported_event_types: Optional[Set[str]] = None
    _observers_by_event_type: Optional[Dict[str, Tuple[Observer, ...]]] = None
    _observers_for_unknown_event_type: Tuple[Observer, ...] = ()
    _capture_event_types: Optional[Set[str]] = None
    _capture_unknown_event_types: bool = False
    _recorded_events: Optional[Deque[Event]] = None
    _lock: "threading.RLock" = threading.RLock()

    def _get_observers(self) -> List[Observer]:
        observers = self.observers
        if observers is None:
            observers = []
            self.observers = observers
        return observers

    def _ensure_recorded_events(self) -> Deque[Event]:
        recorded_events = self._recorded_events
        if recorded_events is None:
            recorded_events = cast("Deque[Event]", deque())  # pragma: allow-cast deque typed narrowing
            self._recorded_events = recorded_events
        return recorded_events

    def _supports_safely(self, observer: Observer, event_type: str) -> bool:
        try:
            return observer.supports(event_type)
        except Exception:  # noqa: BLE001
            return False

    def _infer_eventdispatch_observer_event_types(
        self,
        observer: EventDispatchObserver,
    ) -> Tuple[str, ...]:
        dispatch_map_value = observer.dispatch_map
        if not isinstance(dispatch_map_value, dict):
            return ()

        supported: List[str] = []
        for event_type, handler_name in dispatch_map_value.items():
            if not isinstance(event_type, str) or not isinstance(handler_name, str):
                continue
            if event_type not in CATALOG_EVENT_TYPES_SET:
                continue
            handler = getattr(observer, handler_name, None)  # pragma: allow-dynattr dispatch: observer handler
            if handler is None or not callable(handler):
                continue
            supported.append(event_type)
        return tuple(supported)

    def _infer_observer_subscriptions(self, observer: Observer) -> Tuple[str, ...]:
        try:
            supports_attr = type(observer).supports
        except AttributeError:
            # 允许鸭子类型的 `observer` (例如仅实现了 `on_event`).
            supports_attr = Observer.supports
        try:
            event_types_value = observer.event_types
        except AttributeError:
            event_types_value = None
        event_types = validate_event_types(observer, event_types_value)
        on_event_attr = type(observer).on_event

        if (
            isinstance(observer, EventDispatchObserver)
            and on_event_attr is EventDispatchObserver.on_event
            and event_types is None
            and supports_attr is Observer.supports
        ):
            return self._infer_eventdispatch_observer_event_types(observer)

        if supports_attr is Observer.supports:
            if event_types is None:
                return CATALOG_EVENT_TYPES
            return tuple(event_type for event_type in event_types if event_type in CATALOG_EVENT_TYPES_SET)

        supported: List[str] = []
        for event_type in CATALOG_EVENT_TYPES:
            if self._supports_safely(observer, event_type):
                supported.append(event_type)
        return tuple(supported)

    def _rebuild_subscription_cache(self) -> None:
        observers_by_event_type: Dict[str, List[Observer]] = {event_type: [] for event_type in CATALOG_EVENT_TYPES}
        # 需要接收未知事件类型的观察者(显式选择加入).
        unknown_observers: List[Observer] = []

        observers = self._get_observers()
        for observer in observers:
            observer_event_types = self._infer_observer_subscriptions(observer)
            for event_type in observer_event_types:
                observers_by_event_type[event_type].append(observer)
            supports_unknown = False
            try:
                supports_unknown = bool(observer.supports_unknown_event_types)
            except AttributeError:
                supports_unknown = False
            if supports_unknown:
                unknown_observers.append(observer)

        supported_event_types: Set[str] = {event_type for event_type, observers in observers_by_event_type.items() if observers}

        self._has_observers = bool(observers)
        self._supports_all = len(supported_event_types) == len(observers_by_event_type)
        self._supported_event_types = supported_event_types
        self._observers_by_event_type = {
            event_type: tuple(observers) for event_type, observers in observers_by_event_type.items() if observers
        }
        self._observers_for_unknown_event_type = tuple(unknown_observers)

    def _should_emit_event_type(self, event_type: str) -> bool:
        if self.mode == "capture":
            if self._capture_event_types is None:
                return True
            return event_type in self._capture_event_types
        if not self._has_observers:
            return False
        supported_event_types = self._supported_event_types
        if supported_event_types is None:
            return False
        return event_type in supported_event_types

    def register(self, observer: Observer) -> None:
        with self._lock:
            try:
                event_types_value = observer.event_types
            except AttributeError:
                event_types_value = None
            _ = validate_event_types(observer, event_types_value)
            self._has_observers = True
            self._get_observers().append(observer)
            self._rebuild_subscription_cache()

    def unregister(self, observer: Observer) -> bool:
        with self._lock:
            try:
                self._get_observers().remove(observer)
            except ValueError:
                return False
            self._rebuild_subscription_cache()
            return True

    def clear(self) -> None:
        with self._lock:
            self._get_observers().clear()
            self._ensure_recorded_events().clear()
            self._rebuild_subscription_cache()

    def wants(self, event_type: str) -> bool:
        if event_type in CATALOG_EVENT_TYPES_SET:
            return self._should_emit_event_type(event_type)
        if self.mode == "capture":
            return self._capture_unknown_event_types
        if not self._has_observers:
            return False
        return bool(self._observers_for_unknown_event_type)


__all__ = []
