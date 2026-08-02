from abc import ABC
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from ..._internal.utils.loader_result import LoaderResultPolicy, LoaderResultPolicyValue
from ...events import Event, EventType
from ...vendor.compact.typing_extensionsx import Protocol, Self
from .._dispatch import HookDispatchStrategy

if TYPE_CHECKING:
    import threading


class ExecutionHookLike(Protocol):
    def on_pipeline_start(self, event: Event) -> None: ...

    def on_pipeline_end(self, event: Event) -> None: ...

    def on_batch_start(self, event: Event) -> None: ...

    def on_batch_end(self, event: Event) -> None: ...

    def on_loader_call(self, event: Event) -> None: ...

    def on_field_compute(self, event: Event) -> None: ...

    def on_error(self, event: Event) -> None: ...

    def on_diagnostic_warning(self, event: Event) -> None: ...

    def on_field_slim(self, event: Event) -> None: ...

    def on_row_write(self, event: Event) -> None: ...

    def on_row_release(self, event: Event) -> None: ...

    def on_loader_slim(self, event: Event) -> None: ...

    def on_column_write(self, event: Event) -> None: ...

    def on_pre_use_batch_size(self, decision: Any) -> None: ...


HookTypedHandler = Callable[[Event], Any]
HookOnEventHandler = Callable[[Event], Any]
HookTypedHandlerPair = Tuple[ExecutionHookLike, HookTypedHandler]
HookOnEventHandlerPair = Tuple[ExecutionHookLike, HookOnEventHandler]


class HookManagerLike(Protocol):
    hooks: List[ExecutionHookLike]
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: LoaderResultPolicyValue
    loader_result_sample_size: int

    def _normalize_loader_result_policy(self, policy: LoaderResultPolicy) -> LoaderResultPolicyValue: ...

    @property
    def has_hooks(self) -> bool: ...

    @has_hooks.setter
    def has_hooks(self, value: bool) -> None: ...

    @property
    def typed_handlers_by_event_type(self) -> Dict[EventType, Tuple[HookTypedHandlerPair, ...]]: ...

    @typed_handlers_by_event_type.setter
    def typed_handlers_by_event_type(self, value: Dict[EventType, Tuple[HookTypedHandlerPair, ...]]) -> None: ...

    @property
    def on_event_handlers_by_event_type(self) -> Dict[EventType, Tuple[HookOnEventHandlerPair, ...]]: ...

    @on_event_handlers_by_event_type.setter
    def on_event_handlers_by_event_type(self, value: Dict[EventType, Tuple[HookOnEventHandlerPair, ...]]) -> None: ...

    @property
    def lock(self) -> "threading.RLock": ...

    @lock.setter
    def lock(self, value: "threading.RLock") -> None: ...

    @property
    def diagnostic_warning_emitted(self) -> bool: ...

    @diagnostic_warning_emitted.setter
    def diagnostic_warning_emitted(self, value: bool) -> None: ...

    @property
    def dispatch_strategy(self) -> HookDispatchStrategy: ...

    @dispatch_strategy.setter
    def dispatch_strategy(self, value: HookDispatchStrategy) -> None: ...

    @property
    def base_hook_on_event(self) -> Optional[Callable[..., None]]: ...

    @base_hook_on_event.setter
    def base_hook_on_event(self, value: Optional[Callable[..., None]]) -> None: ...

    @property
    def base_hook_typed_handlers(self) -> Dict[str, Optional[Callable[..., None]]]: ...

    @base_hook_typed_handlers.setter
    def base_hook_typed_handlers(self, value: Dict[str, Optional[Callable[..., None]]]) -> None: ...


class HookManagerBase(HookManagerLike, ABC):
    def _manager(self) -> Self:
        # `mixin` 内部使用时, `_manager()` 仅用于把 `self` 视作统一的“管理器接口”,无需再通过 `cast(object, ...)` 绕过检查器.
        return self

    def _rebuild_subscription_cache(self) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    def _summarize_result(self, result: Any) -> Dict[str, Any]:  # pragma: no cover  # pragma: allow-no-cover abstract method
        _ = result
        raise NotImplementedError

    def _sample_result(self, result: Any) -> Any:  # pragma: no cover  # pragma: allow-no-cover abstract method
        _ = result
        raise NotImplementedError


__all__ = ()
