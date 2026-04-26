# region imports

import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .._internal.utils.loader_result import LoaderResultPolicy, LoaderResultPolicyLike
from ..events import Event
from ..events._events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowReleaseEvent,
    RowWriteEvent,
)
from ..vendor.compact.typing_extensionsx import override
from ._dispatch import HookDispatchStrategy
from ._internal.common import HOOK_TYPED_DISPATCH_MAP
from ._internal.manager_base import ExecutionHookLike, HookOnEventHandlerPair, HookTypedHandlerPair
from ._internal.manager_events import HookManagerEventMixin
from ._internal.manager_registry import HookManagerRegistryMixin
from ._internal.manager_state import HookManagerStateMixin
from ._internal.manager_subscriptions import HookManagerSubscriptionMixin

# endregion


class IExecutionHook(ABC):
    """执行钩子接口."""

    @abstractmethod
    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        """当管线开始时调用."""

    @abstractmethod
    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        """当管线结束时调用."""

    @abstractmethod
    def on_batch_start(self, event: BatchStartEvent) -> None:
        """当批次开始时调用."""

    @abstractmethod
    def on_batch_end(self, event: BatchEndEvent) -> None:
        """当批次结束时调用."""

    @abstractmethod
    def on_loader_call(self, event: LoaderCallEvent) -> None:
        """当加载函数被调用时调用."""

    @abstractmethod
    def on_field_compute(self, event: FieldComputeEvent) -> None:
        """当字段被计算时调用"""

    @abstractmethod
    def on_error(self, event: ErrorEvent) -> None:
        """当发生错误时调用"""

    @abstractmethod
    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        """当发生诊断告警时调用"""

    @abstractmethod
    def on_field_slim(self, event: FieldSlimEvent) -> None:
        """当字段从上下文中删除时调用 (FR022)"""

    @abstractmethod
    def on_row_write(self, event: RowWriteEvent) -> None:
        """当行被写入行式输出端时调用 (FR023)."""

    @abstractmethod
    def on_row_release(self, event: RowReleaseEvent) -> None:
        """当行的内存被释放时调用 (FR023)"""

    @abstractmethod
    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        """当加载结果被压缩时调用 (FR022)."""

    @abstractmethod
    def on_column_write(self, event: ColumnWriteEvent) -> None:
        """当列被写入列式输出端时调用 (FR023)."""

    def on_pre_use_batch_size(self, decision: Any) -> None:
        """策略决策钩子: 在使用 `batch_size` 前允许钩子改写候选值 (`opt-in`)."""
        _ = decision


Hook = IExecutionHook


class BaseHook(IExecutionHook):
    """带有空操作方法的基础钩子实现."""

    event_types: Optional[Set[str]] = None

    def on_event(self, event: Event) -> None:
        """统一事件回调(用于订阅事件目录中的全部事件)."""
        _ = event

    @override
    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        """空操作实现"""

    @override
    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        """空操作实现"""

    @override
    def on_batch_start(self, event: BatchStartEvent) -> None:
        """空操作实现"""

    @override
    def on_batch_end(self, event: BatchEndEvent) -> None:
        """空操作实现"""

    @override
    def on_loader_call(self, event: LoaderCallEvent) -> None:
        """空操作实现"""

    @override
    def on_field_compute(self, event: FieldComputeEvent) -> None:
        """空操作实现"""

    @override
    def on_error(self, event: ErrorEvent) -> None:
        """空操作实现"""

    @override
    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        """空操作实现"""

    @override
    def on_field_slim(self, event: FieldSlimEvent) -> None:
        """空操作实现"""

    @override
    def on_row_write(self, event: RowWriteEvent) -> None:
        """空操作实现"""

    @override
    def on_row_release(self, event: RowReleaseEvent) -> None:
        """空操作实现"""

    @override
    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        """空操作实现"""

    @override
    def on_column_write(self, event: ColumnWriteEvent) -> None:
        """空操作实现"""

    @override
    def on_pre_use_batch_size(self, decision: Any) -> None:
        """策略决策钩子: 在使用 `batch_size` 前允许钩子改写候选值 (`opt-in`)."""
        _ = decision


class HookManager(HookManagerStateMixin, HookManagerSubscriptionMixin, HookManagerRegistryMixin, HookManagerEventMixin):
    """钩子管理器 - 管理并触发所有钩子.

    注意: 请使用 `register`/`unregister`/`clear` 管理钩子,不要直接修改 `hooks` 列表,否则 `fastpath` 缓存可能失效.
    """

    hooks: List[ExecutionHookLike]
    _has_hooks: bool
    _typed_handlers_by_event_type: Dict[str, Tuple[HookTypedHandlerPair, ...]]
    _on_event_handlers_by_event_type: Dict[str, Tuple[HookOnEventHandlerPair, ...]]
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: LoaderResultPolicy
    loader_result_sample_size: int
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool
    _dispatch_strategy: HookDispatchStrategy
    _base_hook_on_event: Optional[Callable[..., None]]
    _base_hook_typed_handlers: Dict[str, Optional[Callable[..., None]]]

    def __init__(
        self,
        enable_debugging: bool = False,  # noqa: FBT001, FBT002
        fallback_logger_enabled: bool = False,  # noqa: FBT001, FBT002
        loader_result_policy: LoaderResultPolicyLike = "full",
        loader_result_sample_size: int = 5,
        dispatch_strategy: Optional[HookDispatchStrategy] = None,
    ) -> None:
        self.hooks = []
        self._has_hooks = False
        self._typed_handlers_by_event_type = {}
        self._on_event_handlers_by_event_type = {}
        self._base_hook_on_event = BaseHook.__dict__.get("on_event")
        self._base_hook_typed_handlers = {name: BaseHook.__dict__.get(name) for name in HOOK_TYPED_DISPATCH_MAP.values()}
        self.debug_mode = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = self._normalize_loader_result_policy(loader_result_policy)
        self.loader_result_sample_size = max(1, loader_result_sample_size)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False
        self._dispatch_strategy = dispatch_strategy or HookDispatchStrategy()

    @property
    @override
    def has_hooks(self) -> bool:
        return self._has_hooks

    @has_hooks.setter
    @override
    def has_hooks(self, value: bool) -> None:
        self._has_hooks = value

    @property
    @override
    def typed_handlers_by_event_type(self) -> Dict[str, Tuple[HookTypedHandlerPair, ...]]:
        return self._typed_handlers_by_event_type

    @typed_handlers_by_event_type.setter
    @override
    def typed_handlers_by_event_type(self, value: Dict[str, Tuple[HookTypedHandlerPair, ...]]) -> None:
        self._typed_handlers_by_event_type = value

    @property
    @override
    def on_event_handlers_by_event_type(self) -> Dict[str, Tuple[HookOnEventHandlerPair, ...]]:
        return self._on_event_handlers_by_event_type

    @on_event_handlers_by_event_type.setter
    @override
    def on_event_handlers_by_event_type(self, value: Dict[str, Tuple[HookOnEventHandlerPair, ...]]) -> None:
        self._on_event_handlers_by_event_type = value

    @property
    @override
    def lock(self) -> "threading.RLock":
        return self._lock

    @lock.setter
    @override
    def lock(self, value: "threading.RLock") -> None:
        self._lock = value

    @property
    @override
    def diagnostic_warning_emitted(self) -> bool:
        return self._diagnostic_warning_emitted

    @diagnostic_warning_emitted.setter
    @override
    def diagnostic_warning_emitted(self, value: bool) -> None:
        self._diagnostic_warning_emitted = value

    @property
    @override
    def dispatch_strategy(self) -> HookDispatchStrategy:
        return self._dispatch_strategy

    @dispatch_strategy.setter
    @override
    def dispatch_strategy(self, value: HookDispatchStrategy) -> None:
        self._dispatch_strategy = value

    @property
    @override
    def base_hook_on_event(self) -> Optional[Callable[..., None]]:
        return self._base_hook_on_event

    @base_hook_on_event.setter
    @override
    def base_hook_on_event(self, value: Optional[Callable[..., None]]) -> None:
        self._base_hook_on_event = value

    @property
    @override
    def base_hook_typed_handlers(self) -> Dict[str, Optional[Callable[..., None]]]:
        return self._base_hook_typed_handlers

    @base_hook_typed_handlers.setter
    @override
    def base_hook_typed_handlers(self, value: Dict[str, Optional[Callable[..., None]]]) -> None:
        self._base_hook_typed_handlers = value


__all__ = ()
