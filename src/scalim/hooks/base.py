# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
# region imports

import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..events.event import Event
from ..events.events import (
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
from ._internal.common import _HOOK_TYPED_DISPATCH_MAP, HOOK_RAISED_EXCEPTION_WARNING  # noqa: F401
from ._internal.manager_events import HookManagerEventMixin
from ._internal.manager_registry import HookManagerRegistryMixin
from ._internal.manager_state import HookManagerStateMixin
from ._internal.manager_subscriptions import HookManagerSubscriptionMixin
from .dispatch import HookDispatchStrategy

# endregion

_TypedHandlerPair = Tuple["IExecutionHook", Callable[[Any], Any]]
_OnEventHandlerPair = Tuple["IExecutionHook", Callable[[Event], Any]]


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


class HookManager(HookManagerStateMixin, HookManagerSubscriptionMixin, HookManagerRegistryMixin, HookManagerEventMixin):
    """钩子管理器 - 管理并触发所有钩子.

    注意: 请使用 `register`/`unregister`/`clear` 管理钩子,不要直接修改 `hooks` 列表,否则 `fastpath` 缓存可能失效.
    """

    hooks: List[IExecutionHook]
    _has_hooks: bool
    _typed_handlers_by_event_type: Dict[str, Tuple[_TypedHandlerPair, ...]]
    _on_event_handlers_by_event_type: Dict[str, Tuple[_OnEventHandlerPair, ...]]
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: str
    loader_result_sample_size: int
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool
    _dispatch_strategy: HookDispatchStrategy

    def __init__(
        self,
        enable_debugging: bool = False,  # noqa: FBT001, FBT002
        fallback_logger_enabled: bool = False,  # noqa: FBT001, FBT002
        loader_result_policy: str = "full",
        loader_result_sample_size: int = 5,
        dispatch_strategy: Optional[HookDispatchStrategy] = None,
    ) -> None:
        self.hooks = []
        self._has_hooks = False
        self._typed_handlers_by_event_type = {}
        self._on_event_handlers_by_event_type = {}
        self._base_hook_on_event = BaseHook.__dict__.get("on_event")
        self._base_hook_typed_handlers = {name: BaseHook.__dict__.get(name) for name in _HOOK_TYPED_DISPATCH_MAP.values()}
        self.debug_mode = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = self._normalize_loader_result_policy(loader_result_policy)
        self.loader_result_sample_size = max(1, loader_result_sample_size)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False
        self._dispatch_strategy = dispatch_strategy or HookDispatchStrategy()


__all__ = [
    "BaseHook",
    "Hook",
    "HookManager",
    "IExecutionHook",
]
