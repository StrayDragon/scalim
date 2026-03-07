# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
import contextlib
import threading
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple, cast

from ..dispatch import HookDispatchStrategy


class HookManagerStateMixin:
    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        state.pop("_typed_handlers_by_event_type", None)
        state.pop("_on_event_handlers_by_event_type", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()
        hooks_obj = state.get("hooks", self.__dict__.get("hooks", []))
        if isinstance(hooks_obj, list):
            self.hooks = hooks_obj
        elif hooks_obj:
            self.hooks = list(hooks_obj)
        else:
            self.hooks = []

        self._base_hook_on_event = state.get("_base_hook_on_event", self.__dict__.get("_base_hook_on_event"))
        self._base_hook_typed_handlers = state.get("_base_hook_typed_handlers", self.__dict__.get("_base_hook_typed_handlers", {}))

        if "_has_hooks" in state:
            self._has_hooks = bool(state["_has_hooks"])
        else:
            self._has_hooks = bool(self.hooks)

        self._typed_handlers_by_event_type = {}
        self._on_event_handlers_by_event_type = {}

        dispatch_strategy = state.get("_dispatch_strategy")
        if isinstance(dispatch_strategy, HookDispatchStrategy):
            self._dispatch_strategy = dispatch_strategy
        else:
            self._dispatch_strategy = HookDispatchStrategy()
        self._rebuild_subscription_cache()

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
            mapping = cast("Mapping[Any, Any]", result)
            sample = dict(list(mapping.items())[: self.loader_result_sample_size])
        elif isinstance(result, list):
            items = cast("List[Any]", result)
            sample = items[: self.loader_result_sample_size]
        elif isinstance(result, tuple):
            items = cast("Tuple[Any, ...]", result)
            sample = list(items[: self.loader_result_sample_size])
        elif isinstance(result, AbstractSet):
            sample = list(islice(cast("Set[Any]", result), self.loader_result_sample_size))
        elif isinstance(result, (str, bytes)):
            sample = result[: self.loader_result_sample_size]
        elif isinstance(result, SequenceABC):
            sequence = cast("Sequence[Any]", result)
            with contextlib.suppress(Exception):
                sample = list(sequence[: self.loader_result_sample_size])
        if sample is None:
            return self._summarize_result(cast("Any", result))
        return sample
