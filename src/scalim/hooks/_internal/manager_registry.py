# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from typing import Any

from .common import _read_optional_attr, _validate_event_types


class HookManagerRegistryMixin:
    def register(self, hook: Any) -> None:
        with self._lock:
            _ = _validate_event_types(hook, _read_optional_attr(hook, "event_types"))
            self._has_hooks = True
            self.hooks.append(hook)
            self._rebuild_subscription_cache()

    def unregister(self, hook: Any) -> bool:
        with self._lock:
            try:
                self.hooks.remove(hook)
            except ValueError:
                return False
            self._has_hooks = bool(self.hooks)
            self._rebuild_subscription_cache()
            return True

    def clear(self) -> None:
        with self._lock:
            self.hooks.clear()
            self._has_hooks = False
            self._rebuild_subscription_cache()
