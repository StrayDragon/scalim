from abc import ABC
from typing import Dict, List, Optional, Set, Tuple, cast

from ...vendor.compact.typing_extensionsx import override
from .common import (
    CATALOG_EVENT_TYPES,
    HOOK_TYPED_DISPATCH_MAP,
    read_callable_attr,
    read_optional_attr,
    resolve_mro_attr,
    validate_event_types,
)
from .manager_base import (
    ExecutionHookLike,
    HookManagerBase,
    HookOnEventHandler,
    HookOnEventHandlerPair,
    HookTypedHandler,
    HookTypedHandlerPair,
)


class HookManagerSubscriptionMixin(HookManagerBase, ABC):
    def _hook_overrides_on_event(self, hook: ExecutionHookLike) -> bool:
        manager = self._manager()
        on_event_attr = resolve_mro_attr(type(hook), "on_event")
        if on_event_attr is None:
            return False
        return on_event_attr is not manager.base_hook_on_event

    def _iter_hook_typed_subscriptions(self, hook: ExecutionHookLike) -> Tuple[str, ...]:
        manager = self._manager()
        hook_type = type(hook)
        subscribed: List[str] = []
        for event_type, handler_name in HOOK_TYPED_DISPATCH_MAP.items():
            hook_handler = resolve_mro_attr(hook_type, handler_name)
            if hook_handler is None:
                continue
            base_handler = manager.base_hook_typed_handlers.get(handler_name)
            if base_handler is not None and hook_handler is base_handler:
                continue
            subscribed.append(event_type)
        return tuple(subscribed)

    def _append_hook_typed_handlers(
        self,
        hook: ExecutionHookLike,
        event_types: Optional[Set[str]],
        typed_handlers_by_type: Dict[str, List[HookTypedHandlerPair]],
    ) -> None:
        for event_type in self._iter_hook_typed_subscriptions(hook):
            if event_types is not None and event_type not in event_types:
                continue
            handler_name = HOOK_TYPED_DISPATCH_MAP[event_type]
            handler = read_callable_attr(hook, handler_name)
            if handler is None:
                continue
            typed_handlers_by_type[event_type].append(
                (hook, cast("HookTypedHandler", handler))  # pragma: allow-cast hook method typed narrowing
            )

    def _append_hook_on_event_handlers(
        self,
        hook: ExecutionHookLike,
        event_types: Optional[Set[str]],
        on_event_handlers_by_type: Dict[str, List[HookOnEventHandlerPair]],
    ) -> None:
        if not self._hook_overrides_on_event(hook):
            return
        on_event_handler = read_callable_attr(hook, "on_event")
        if on_event_handler is None:
            return
        typed_on_event_handler = cast("HookOnEventHandler", on_event_handler)  # pragma: allow-cast hook method typed narrowing
        if event_types is None:
            for event_type in CATALOG_EVENT_TYPES:
                on_event_handlers_by_type[event_type].append((hook, typed_on_event_handler))
            return
        for event_type in event_types:
            if event_type in on_event_handlers_by_type:
                on_event_handlers_by_type[event_type].append((hook, typed_on_event_handler))

    @override
    def _rebuild_subscription_cache(self) -> None:
        manager = self._manager()
        typed_handlers_by_type: Dict[str, List[HookTypedHandlerPair]] = {event_type: [] for event_type in HOOK_TYPED_DISPATCH_MAP}
        on_event_handlers_by_type: Dict[str, List[HookOnEventHandlerPair]] = {event_type: [] for event_type in CATALOG_EVENT_TYPES}

        for hook in manager.hooks:
            event_types = validate_event_types(hook, read_optional_attr(hook, "event_types"))
            self._append_hook_typed_handlers(hook, event_types, typed_handlers_by_type)
            self._append_hook_on_event_handlers(hook, event_types, on_event_handlers_by_type)

        manager.has_hooks = bool(manager.hooks)
        manager.typed_handlers_by_event_type = {key: tuple(value) for key, value in typed_handlers_by_type.items() if value}
        manager.on_event_handlers_by_event_type = {key: tuple(value) for key, value in on_event_handlers_by_type.items() if value}

    def wants_typed(self, event_type: str) -> bool:
        manager = self._manager()
        if not manager.has_hooks:
            return False
        return event_type in manager.typed_handlers_by_event_type

    def wants_on_event(self, event_type: str) -> bool:
        manager = self._manager()
        if not manager.has_hooks:
            return False
        return event_type in manager.on_event_handlers_by_event_type

    def wants(self, event_type: str) -> bool:
        return self.wants_typed(event_type) or self.wants_on_event(event_type)


__all__ = ()
