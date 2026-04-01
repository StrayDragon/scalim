from abc import ABC

from .common import read_optional_attr, validate_event_types
from .manager_base import ExecutionHookLike, HookManagerBase


class HookManagerRegistryMixin(HookManagerBase, ABC):
    def register(self, hook: ExecutionHookLike) -> None:
        manager = self._manager()
        with manager.lock:
            _ = validate_event_types(hook, read_optional_attr(hook, "event_types"))
            manager.has_hooks = True
            manager.hooks.append(hook)
            self._rebuild_subscription_cache()

    def unregister(self, hook: ExecutionHookLike) -> bool:
        manager = self._manager()
        with manager.lock:
            try:
                manager.hooks.remove(hook)
            except ValueError:
                return False
            manager.has_hooks = bool(manager.hooks)
            self._rebuild_subscription_cache()
            return True

    def clear(self) -> None:
        manager = self._manager()
        with manager.lock:
            manager.hooks.clear()
            manager.has_hooks = False
            self._rebuild_subscription_cache()


__all__ = ()
