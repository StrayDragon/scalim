import contextlib
import threading
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple, cast

from ...vendor.compact.typing_extensionsx import override
from ..dispatch import HookDispatchStrategy
from .manager_base import ExecutionHookLike, HookManagerBase, HookOnEventHandlerPair, HookTypedHandlerPair


class HookManagerStateMixin(HookManagerBase):
    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        state.pop("_typed_handlers_by_event_type", None)
        state.pop("_on_event_handlers_by_event_type", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        manager = self._manager()
        self.__dict__.update(state)
        manager.lock = threading.RLock()

        hooks_obj = state.get("hooks", self.__dict__.get("hooks", []))
        if isinstance(hooks_obj, list):
            manager.hooks = cast("List[ExecutionHookLike]", hooks_obj)
        elif hooks_obj:
            manager.hooks = cast("List[ExecutionHookLike]", list(hooks_obj))
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
        self._rebuild_subscription_cache()

    def _normalize_loader_result_policy(self, policy: str) -> str:
        normalized = (policy or "full").lower()
        if normalized not in ("full", "summary", "sample", "none"):
            msg = "Unknown loader_result_policy: '{}'".format(policy)
            raise ValueError(msg)
        return normalized

    @override
    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        summary: Dict[str, Any] = {"type": type(result).__name__}
        if isinstance(result, SizedABC):
            with contextlib.suppress(Exception):
                summary["size"] = len(result)
        return summary

    @override
    def _sample_result(self, result: Any) -> Any:
        sample_size = self._manager().loader_result_sample_size
        sample: Any = None
        if isinstance(result, MappingABC):
            mapping = cast("Mapping[Any, Any]", result)
            sample = dict(list(mapping.items())[:sample_size])
        elif isinstance(result, list):
            items = cast("List[Any]", result)
            sample = items[:sample_size]
        elif isinstance(result, tuple):
            items = cast("Tuple[Any, ...]", result)
            sample = list(items[:sample_size])
        elif isinstance(result, AbstractSet):
            sample = list(islice(cast("Set[Any]", result), sample_size))
        elif isinstance(result, (str, bytes)):
            sample = result[:sample_size]
        elif isinstance(result, SequenceABC):
            sequence = cast("Sequence[Any]", result)
            with contextlib.suppress(Exception):
                sample = list(sequence[:sample_size])
        if sample is None:
            return self._summarize_result(result)
        return sample
