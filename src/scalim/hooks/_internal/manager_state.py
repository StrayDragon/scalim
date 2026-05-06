import threading
from abc import ABC
from typing import Any, Dict, Tuple

from ..._internal.utils.loader_result import (
    LoaderResultPolicy,
    LoaderResultPolicyValue,
    normalize_loader_result_policy,
    parse_loader_result_policy,
    sample_loader_result,
    summarize_loader_result,
)
from ...vendor.compact.typing_extensionsx import override
from .._dispatch import HookDispatchStrategy
from .manager_base import HookManagerBase, HookOnEventHandlerPair, HookTypedHandlerPair


class HookManagerStateMixin(HookManagerBase, ABC):
    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        state.pop("_typed_handlers_by_event_type", None)
        state.pop("_on_event_handlers_by_event_type", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        manager = self._manager()
        vars(self).update(state)
        manager.lock = threading.RLock()

        hooks_obj = state.get("hooks", self.__dict__.get("hooks", []))
        if isinstance(hooks_obj, list):
            manager.hooks = hooks_obj
        elif hooks_obj:
            manager.hooks = list(hooks_obj)
        else:
            manager.hooks = []

        manager.base_hook_on_event = state.get("_base_hook_on_event", self.__dict__.get("_base_hook_on_event"))
        manager.base_hook_typed_handlers = state.get("_base_hook_typed_handlers", self.__dict__.get("_base_hook_typed_handlers", {}))

        if "_has_hooks" in state:
            manager.has_hooks = bool(state["_has_hooks"])
        else:
            manager.has_hooks = bool(manager.hooks)

        typed_handlers_by_event_type: Dict[str, Tuple[HookTypedHandlerPair, ...]] = {}
        on_event_handlers_by_event_type: Dict[str, Tuple[HookOnEventHandlerPair, ...]] = {}
        manager.typed_handlers_by_event_type = typed_handlers_by_event_type
        manager.on_event_handlers_by_event_type = on_event_handlers_by_event_type

        dispatch_strategy = state.get("_dispatch_strategy")
        if isinstance(dispatch_strategy, HookDispatchStrategy):
            manager.dispatch_strategy = dispatch_strategy
        else:
            manager.dispatch_strategy = HookDispatchStrategy()

        # 确保状态/序列化边界仅存储内置 `str` 字面量值.
        manager.loader_result_policy = parse_loader_result_policy(state.get("loader_result_policy"))
        self._rebuild_subscription_cache()

    @override
    def _normalize_loader_result_policy(self, policy: LoaderResultPolicy) -> LoaderResultPolicyValue:
        return normalize_loader_result_policy(policy)

    @override
    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        return summarize_loader_result(result)

    @override
    def _sample_result(self, result: Any) -> Any:
        return sample_loader_result(result, sample_size=self._manager().loader_result_sample_size)


__all__ = ()
