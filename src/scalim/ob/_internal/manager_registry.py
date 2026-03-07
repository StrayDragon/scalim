# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from typing import Dict, List, Set, Tuple, cast

from ..observer import EventDispatchObserver, Observer
from .common import _CATALOG_EVENT_TYPES, _CATALOG_EVENT_TYPES_SET, _validate_event_types


class ObserverManagerRegistryMixin:
    def _supports_safely(self, observer: Observer, event_type: str) -> bool:
        try:
            return observer.supports(event_type)
        except Exception:  # noqa: BLE001
            return False

    def _infer_eventdispatch_observer_event_types(self, observer: "EventDispatchObserver") -> "Tuple[str, ...]":
        dispatch_map = getattr(observer, "dispatch_map", None)
        if not isinstance(dispatch_map, dict):
            return ()

        dispatch_map = cast("Dict[str, str]", dispatch_map)
        supported: List[str] = []
        for event_type, handler_name in dispatch_map.items():
            if event_type not in _CATALOG_EVENT_TYPES_SET:
                continue
            handler = getattr(observer, handler_name, None)
            if handler is None or not callable(handler):
                continue
            supported.append(event_type)
        return tuple(supported)

    def _infer_observer_subscriptions(self, observer: Observer) -> "Tuple[str, ...]":
        supports_attr = getattr(type(observer), "supports", None)
        event_types = _validate_event_types(observer, getattr(observer, "event_types", None))
        on_event_attr = getattr(type(observer), "on_event", None)

        if (
            isinstance(observer, EventDispatchObserver)
            and on_event_attr is EventDispatchObserver.on_event
            and event_types is None
            and supports_attr is Observer.supports
        ):
            return self._infer_eventdispatch_observer_event_types(observer)

        if supports_attr is Observer.supports:
            if event_types is None:
                return _CATALOG_EVENT_TYPES
            return tuple(event_type for event_type in event_types if event_type in _CATALOG_EVENT_TYPES_SET)

        supported: List[str] = []
        for event_type in _CATALOG_EVENT_TYPES:
            if self._supports_safely(observer, event_type):
                supported.append(event_type)
        return tuple(supported)

    def _rebuild_subscription_cache(self) -> None:
        observers_by_event_type: Dict[str, List[Observer]] = {event_type: [] for event_type in _CATALOG_EVENT_TYPES}
        # 需要接收未知事件类型的观察者(显式选择加入).
        unknown_observers: List[Observer] = []

        for observer in self.observers:
            observer_event_types = self._infer_observer_subscriptions(observer)
            for event_type in observer_event_types:
                observers_by_event_type[event_type].append(observer)
            if getattr(observer, "supports_unknown_event_types", False):
                unknown_observers.append(observer)

        supported_event_types: Set[str] = {event_type for event_type, observers in observers_by_event_type.items() if observers}

        self._has_observers = bool(self.observers)
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
        return event_type in self._supported_event_types

    def register(self, observer: Observer) -> None:
        with self._lock:
            _ = _validate_event_types(observer, getattr(observer, "event_types", None))
            self._has_observers = True
            self.observers.append(observer)
            self._rebuild_subscription_cache()

    def unregister(self, observer: Observer) -> bool:
        with self._lock:
            try:
                self.observers.remove(observer)
            except ValueError:
                return False
            self._rebuild_subscription_cache()
            return True

    def clear(self) -> None:
        with self._lock:
            self.observers.clear()
            self._recorded_events.clear()
            self._rebuild_subscription_cache()

    def wants(self, event_type: str) -> bool:
        if event_type in _CATALOG_EVENT_TYPES_SET:
            return self._should_emit_event_type(event_type)
        if self.mode == "capture":
            return self._capture_unknown_event_types
        if not self._has_observers:
            return False
        return bool(self._observers_for_unknown_event_type)
