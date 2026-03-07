# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ...events.event import Event
from .common import (
    _CATALOG_EVENT_TYPES,
    _HOOK_TYPED_DISPATCH_MAP,
    _read_callable_attr,
    _read_optional_attr,
    _resolve_mro_attr,
    _validate_event_types,
)

_TypedHandlerPair = Tuple[Any, Callable[[Any], Any]]
_OnEventHandlerPair = Tuple[Any, Callable[[Event], Any]]


class HookManagerSubscriptionMixin:
    def _hook_overrides_on_event(self, hook: Any) -> bool:
        on_event_attr = _resolve_mro_attr(type(hook), "on_event")
        if on_event_attr is None:
            return False
        return on_event_attr is not self._base_hook_on_event

    def _iter_hook_typed_subscriptions(self, hook: Any) -> "Tuple[str, ...]":
        hook_type = type(hook)
        subscribed: List[str] = []
        for event_type, handler_name in _HOOK_TYPED_DISPATCH_MAP.items():
            hook_handler = _resolve_mro_attr(hook_type, handler_name)
            if hook_handler is None:
                continue
            base_handler = self._base_hook_typed_handlers.get(handler_name)
            if base_handler is not None and hook_handler is base_handler:
                continue
            subscribed.append(event_type)
        return tuple(subscribed)

    def _append_hook_typed_handlers(
        self,
        hook: Any,
        event_types: Optional[Set[str]],
        typed_handlers_by_type: "Dict[str, List[_TypedHandlerPair]]",
    ) -> None:
        if event_types is None:
            for event_type in self._iter_hook_typed_subscriptions(hook):
                handler_name = _HOOK_TYPED_DISPATCH_MAP[event_type]
                handler = _read_callable_attr(hook, handler_name)
                if handler is None:
                    continue
                typed_handlers_by_type[event_type].append((hook, handler))
            return

        for event_type in self._iter_hook_typed_subscriptions(hook):
            if event_type not in event_types:
                continue
            handler_name = _HOOK_TYPED_DISPATCH_MAP[event_type]
            handler = _read_callable_attr(hook, handler_name)
            if handler is None:
                continue
            typed_handlers_by_type[event_type].append((hook, handler))

    def _append_hook_on_event_handlers(
        self,
        hook: Any,
        event_types: Optional[Set[str]],
        on_event_handlers_by_type: "Dict[str, List[_OnEventHandlerPair]]",
    ) -> None:
        if not self._hook_overrides_on_event(hook):
            return
        on_event_handler = _read_callable_attr(hook, "on_event")
        if on_event_handler is None:
            return
        if event_types is None:
            for event_type in _CATALOG_EVENT_TYPES:
                on_event_handlers_by_type[event_type].append((hook, on_event_handler))
            return
        for event_type in event_types:
            if event_type in on_event_handlers_by_type:
                on_event_handlers_by_type[event_type].append((hook, on_event_handler))

    def _rebuild_subscription_cache(self) -> None:
        typed_handlers_by_type: Dict[str, List[_TypedHandlerPair]] = {event_type: [] for event_type in _HOOK_TYPED_DISPATCH_MAP}
        on_event_handlers_by_type: Dict[str, List[_OnEventHandlerPair]] = {event_type: [] for event_type in _CATALOG_EVENT_TYPES}

        for hook in self.hooks:
            event_types = _validate_event_types(hook, _read_optional_attr(hook, "event_types"))
            self._append_hook_typed_handlers(hook, event_types, typed_handlers_by_type)
            self._append_hook_on_event_handlers(hook, event_types, on_event_handlers_by_type)

        self._has_hooks = bool(self.hooks)
        self._typed_handlers_by_event_type = {key: tuple(value) for key, value in typed_handlers_by_type.items() if value}
        self._on_event_handlers_by_event_type = {key: tuple(value) for key, value in on_event_handlers_by_type.items() if value}

    def wants_typed(self, event_type: str) -> bool:
        if not self._has_hooks:
            return False
        return event_type in self._typed_handlers_by_event_type

    def wants_on_event(self, event_type: str) -> bool:
        if not self._has_hooks:
            return False
        return event_type in self._on_event_handlers_by_event_type

    def wants(self, event_type: str) -> bool:
        return self.wants_typed(event_type) or self.wants_on_event(event_type)
