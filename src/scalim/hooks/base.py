# region imports

import contextlib
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Mapping, Sequence
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, TypeVar, cast

from ..events.catalog import (
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_COLUMN_WRITE,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_ERROR,
    EVENT_FIELD_COMPUTE,
    EVENT_FIELD_SLIM,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_LOADER_SLIM,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_RELATION_LOOKUP,
    EVENT_ROW_RELEASE,
    EVENT_ROW_WRITE,
    EVENT_STAGE_SPAN,
)
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

# endregion

_logger = logging.getLogger(__name__)
_EventT = TypeVar("_EventT")
_TypedHandlerPair = tuple["IExecutionHook", Callable[[Any], Any]]
_OnEventHandlerPair = tuple["IExecutionHook", Callable[[Event], Any]]

_HOOK_TYPED_DISPATCH_MAP: dict[str, str] = {
    EVENT_PIPELINE_START: "on_pipeline_start",
    EVENT_PIPELINE_END: "on_pipeline_end",
    EVENT_BATCH_START: "on_batch_start",
    EVENT_BATCH_END: "on_batch_end",
    EVENT_LOADER_CALL: "on_loader_call",
    EVENT_FIELD_COMPUTE: "on_field_compute",
    EVENT_ERROR: "on_error",
    EVENT_DIAGNOSTIC_WARNING: "on_diagnostic_warning",
    EVENT_FIELD_SLIM: "on_field_slim",
    EVENT_ROW_WRITE: "on_row_write",
    EVENT_ROW_RELEASE: "on_row_release",
    EVENT_LOADER_SLIM: "on_loader_slim",
    EVENT_COLUMN_WRITE: "on_column_write",
}

_CATALOG_EVENT_TYPES: tuple[str, ...] = (
    EVENT_PIPELINE_START,
    EVENT_PIPELINE_END,
    EVENT_BATCH_START,
    EVENT_BATCH_END,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_FIELD_COMPUTE,
    EVENT_ERROR,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_FIELD_SLIM,
    EVENT_ROW_WRITE,
    EVENT_ROW_RELEASE,
    EVENT_LOADER_SLIM,
    EVENT_COLUMN_WRITE,
    EVENT_RELATION_LOOKUP,
    EVENT_STAGE_SPAN,
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
)


class IExecutionHook(ABC):
    """执行钩子接口"""

    @abstractmethod
    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        """当流水线开始时调用"""

    @abstractmethod
    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        """当流水线结束时调用"""

    @abstractmethod
    def on_batch_start(self, event: BatchStartEvent) -> None:
        """当批次开始时调用"""

    @abstractmethod
    def on_batch_end(self, event: BatchEndEvent) -> None:
        """当批次结束时调用"""

    @abstractmethod
    def on_loader_call(self, event: LoaderCallEvent) -> None:
        """当加载器被调用时调用"""

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
        """当行被写入流式写出端时调用 (FR023)"""

    @abstractmethod
    def on_row_release(self, event: RowReleaseEvent) -> None:
        """当行的内存被释放时调用 (FR023)"""

    @abstractmethod
    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        """当加载器结果被压缩时调用 (FR022)"""

    @abstractmethod
    def on_column_write(self, event: ColumnWriteEvent) -> None:
        """当列被写入列式写出端时调用 (FR023)"""


Hook = IExecutionHook


class BaseHook(IExecutionHook):
    """带有空操作方法的基础钩子实现"""

    event_types: set[str] | None = None

    def on_event(self, event: Event) -> None:
        """可选的统一事件钩子 (用于订阅 `events.catalog` 中定义的全部事件)."""
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


class HookManager:
    """钩子管理器 - 管理并触发所有钩子.

    注意: 请使用 `register`/`unregister`/`clear` 管理钩子,不要直接修改钩子列表,否则快速路径缓存可能失效.
    """

    hooks: list[IExecutionHook]
    _has_hooks: bool
    _typed_handlers_by_event_type: dict[str, tuple[_TypedHandlerPair, ...]]
    _on_event_handlers_by_event_type: dict[str, tuple[_OnEventHandlerPair, ...]]
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: str
    loader_result_sample_size: int
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool

    def __init__(
        self,
        enable_debugging: bool = False,  # noqa: FBT001, FBT002
        fallback_logger_enabled: bool = False,  # noqa: FBT001, FBT002
        loader_result_policy: str = "full",
        loader_result_sample_size: int = 5,
    ) -> None:
        self.hooks = []
        self._has_hooks = False
        self._typed_handlers_by_event_type = {}
        self._on_event_handlers_by_event_type = {}
        self.debug_mode = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = self._normalize_loader_result_policy(loader_result_policy)
        self.loader_result_sample_size = max(1, loader_result_sample_size)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False

    def __getstate__(self) -> dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        state.pop("_typed_handlers_by_event_type", None)
        state.pop("_on_event_handlers_by_event_type", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()
        if not hasattr(self, "_has_hooks"):
            self._has_hooks = bool(getattr(self, "hooks", []))
        if not hasattr(self, "_typed_handlers_by_event_type"):
            self._typed_handlers_by_event_type = {}
        if not hasattr(self, "_on_event_handlers_by_event_type"):
            self._on_event_handlers_by_event_type = {}
        self._rebuild_subscription_cache()

    def _normalize_loader_result_policy(self, policy: str) -> str:
        normalized = (policy or "full").lower()
        if normalized not in ("full", "summary", "sample", "none"):
            msg = f"Unknown loader_result_policy: '{policy}'"
            raise ValueError(msg)
        return normalized

    def _summarize_result(self, result: Any) -> dict[str, Any]:
        summary: dict[str, Any] = {"type": type(result).__name__}
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
            items = cast("list[Any]", result)
            sample = items[: self.loader_result_sample_size]
        elif isinstance(result, tuple):
            items = cast("tuple[Any, ...]", result)
            sample = list(items[: self.loader_result_sample_size])
        elif isinstance(result, AbstractSet):
            sample = list(islice(cast("set[Any]", result), self.loader_result_sample_size))
        elif isinstance(result, (str, bytes)):
            sample = result[: self.loader_result_sample_size]
        elif isinstance(result, SequenceABC):
            sequence = cast("Sequence[Any]", result)
            with contextlib.suppress(Exception):
                sample = list(sequence[: self.loader_result_sample_size])
        if sample is None:
            return self._summarize_result(cast("Any", result))
        return sample

    def _hook_overrides_on_event(self, hook: IExecutionHook) -> bool:
        on_event_attr = getattr(type(hook), "on_event", None)
        if on_event_attr is None:
            return False
        return on_event_attr is not BaseHook.on_event

    def _iter_hook_typed_subscriptions(self, hook: IExecutionHook) -> "tuple[str, ...]":
        hook_type = type(hook)
        subscribed: list[str] = []
        for event_type, handler_name in _HOOK_TYPED_DISPATCH_MAP.items():
            hook_handler = getattr(hook_type, handler_name, None)
            if hook_handler is None:
                continue
            base_handler = getattr(BaseHook, handler_name, None)
            # 如果钩子继承了 BaseHook 的空操作实现,则无需订阅该事件.
            if base_handler is not None and hook_handler is base_handler:
                continue
            subscribed.append(event_type)
        return tuple(subscribed)

    def _append_hook_typed_handlers(
        self,
        hook: IExecutionHook,
        event_types: set[str] | None,
        typed_handlers_by_type: "dict[str, list[_TypedHandlerPair]]",
    ) -> None:
        if event_types is None:
            for event_type in self._iter_hook_typed_subscriptions(hook):
                handler_name = _HOOK_TYPED_DISPATCH_MAP[event_type]
                handler = getattr(hook, handler_name, None)
                if handler is None or not callable(handler):
                    continue
                typed_handlers_by_type[event_type].append((hook, handler))
            return

        for event_type in self._iter_hook_typed_subscriptions(hook):
            if event_type not in event_types:
                continue
            handler_name = _HOOK_TYPED_DISPATCH_MAP[event_type]
            handler = getattr(hook, handler_name, None)
            if handler is None or not callable(handler):
                continue
            typed_handlers_by_type[event_type].append((hook, handler))

    def _append_hook_on_event_handlers(
        self,
        hook: IExecutionHook,
        event_types: set[str] | None,
        on_event_handlers_by_type: "dict[str, list[_OnEventHandlerPair]]",
    ) -> None:
        if not self._hook_overrides_on_event(hook):
            return
        on_event_handler = getattr(hook, "on_event", None)
        if on_event_handler is None or not callable(on_event_handler):
            return
        if event_types is None:
            for event_type in _CATALOG_EVENT_TYPES:
                on_event_handlers_by_type[event_type].append((hook, on_event_handler))
            return
        for event_type in event_types:
            if event_type in on_event_handlers_by_type:
                on_event_handlers_by_type[event_type].append((hook, on_event_handler))

    def _rebuild_subscription_cache(self) -> None:
        typed_handlers_by_type: dict[str, list[_TypedHandlerPair]] = {event_type: [] for event_type in _HOOK_TYPED_DISPATCH_MAP}
        on_event_handlers_by_type: dict[str, list[_OnEventHandlerPair]] = {event_type: [] for event_type in _CATALOG_EVENT_TYPES}

        for hook in self.hooks:
            event_types = getattr(hook, "event_types", None)
            self._append_hook_typed_handlers(hook, event_types, typed_handlers_by_type)
            self._append_hook_on_event_handlers(hook, event_types, on_event_handlers_by_type)

        self._has_hooks = bool(self.hooks)
        self._typed_handlers_by_event_type = {key: tuple(value) for key, value in typed_handlers_by_type.items() if value}
        self._on_event_handlers_by_event_type = {key: tuple(value) for key, value in on_event_handlers_by_type.items() if value}

    def _safe_call(
        self,
        hook: IExecutionHook,
        method: Callable[[_EventT], Any],
        event: _EventT,
    ) -> None:
        try:
            method(event)
        except Exception:
            if self.debug_mode:
                raise
            _logger.warning(
                "Hook %s.%s raised exception",
                type(hook).__name__,
                method.__name__,
                exc_info=True,
            )

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

    def register(self, hook: IExecutionHook) -> None:
        with self._lock:
            self._has_hooks = True
            self.hooks.append(hook)
            self._rebuild_subscription_cache()

    def unregister(self, hook: IExecutionHook) -> bool:
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

    def emit_typed(self, event_type: str, payload: Any) -> None:
        """根据 event_type 到处理器的映射触发一次类型化钩子回调.

        注意: 该方法不会构建负载,仅在负载已准备好时进行分发.
        """
        if not self._has_hooks:
            return
        handler_pairs = self._typed_handlers_by_event_type.get(event_type)
        if not handler_pairs:
            return
        for hook, handler in handler_pairs:
            self._safe_call(hook, handler, payload)

    def emit_on_event(self, event: Event) -> None:
        if not self._has_hooks:
            return
        handler_pairs = self._on_event_handlers_by_event_type.get(event.event_type)
        if not handler_pairs:
            return
        for hook, handler in handler_pairs:
            self._safe_call(hook, handler, event)

    def trigger_pipeline_start(self, targets: list[str], batch_size: int) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_PIPELINE_START)
            if not handler_pairs:
                return
            event = PipelineStartEvent(targets, batch_size)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_PIPELINE_END)
            if not handler_pairs:
                return
            event = PipelineEndEvent(total_batches, total_duration)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_batch_start(self, batch_num: int, row_ids: list[Any]) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_BATCH_START)
            if not handler_pairs:
                return
            event = BatchStartEvent(batch_num, row_ids)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_batch_end(self, batch_num: int, duration: float) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_BATCH_END)
            if not handler_pairs:
                return
            event = BatchEndEvent(batch_num, duration)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_loader_call(
        self,
        loader_name: str,
        params: dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: int | None = None,
        cache_status: str | None = None,
        cache_scope: str | None = None,
        lookup_key_count: int | None = None,
        field_keys: list[str] | None = None,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_LOADER_CALL)
            if not handler_pairs:
                return

            payload = result
            if self.loader_result_policy != "full":
                if self.loader_result_policy == "none":
                    payload = None
                elif self.loader_result_policy == "summary":
                    payload = self._summarize_result(result)
                elif self.loader_result_policy == "sample":
                    payload = self._sample_result(result)
            event = LoaderCallEvent(
                loader_name=loader_name,
                params=params,
                result=payload,
                duration=duration,
                batch_num=batch_num,
                cache_status=cache_status,
                cache_scope=cache_scope,
                lookup_key_count=lookup_key_count,
                field_keys=field_keys,
            )
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_field_compute(
        self,
        field_key: str,
        row_id: Hashable,
        dependencies: dict[str, Any],
        result: Any,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_FIELD_COMPUTE)
            if not handler_pairs:
                return
            event = FieldComputeEvent(field_key, row_id, dependencies, result)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_error(self, error: Exception, context: dict[str, Any]) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ERROR)
            if not handler_pairs:
                return
            event = ErrorEvent(error, context)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_diagnostic_warning(
        self,
        message: str,
        source_id: str,
        field_id: str,
        lookup_key: Any,
        row_id: Hashable,
        *,
        sample_once: bool = False,
    ) -> None:
        with self._lock:
            if sample_once and self._diagnostic_warning_emitted:
                return
            if sample_once:
                self._diagnostic_warning_emitted = True

            if self.hooks:
                handler_pairs = self._typed_handlers_by_event_type.get(EVENT_DIAGNOSTIC_WARNING)
                if not handler_pairs:
                    return
                event = DiagnosticWarningEvent(
                    message=message,
                    source_id=source_id,
                    field_id=field_id,
                    lookup_key=lookup_key,
                    row_id=row_id,
                )
                for hook, handler in handler_pairs:
                    self._safe_call(hook, handler, event)
                return

            self._has_hooks = False

        if self.fallback_logger_enabled:
            _logger.warning(
                "[诊断] %s | source=%s field=%s row_id=%s lookup_key=%r",
                message,
                source_id,
                field_id,
                row_id,
                lookup_key,
            )

    def trigger_field_slim(
        self,
        field_key: str,
        reason: str,
        batch_num: int,
        remaining_fields: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_FIELD_SLIM)
            if not handler_pairs:
                return
            event = FieldSlimEvent(field_key, reason, batch_num, remaining_fields)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_row_write(
        self,
        row_id: Hashable,
        field_count: int,
        batch_num: int,
        row_index: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ROW_WRITE)
            if not handler_pairs:
                return
            event = RowWriteEvent(row_id, field_count, batch_num, row_index)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_row_release(
        self,
        row_id: Hashable,
        released_fields: list[str],
        retained_fields: list[str],
        batch_num: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ROW_RELEASE)
            if not handler_pairs:
                return
            event = RowReleaseEvent(row_id, released_fields, retained_fields, batch_num)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_loader_slim(
        self,
        loader_name: str,
        original_keys: int,
        extracted_fields: list[str],
        batch_num: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_LOADER_SLIM)
            if not handler_pairs:
                return
            event = LoaderSlimEvent(loader_name, original_keys, extracted_fields, batch_num)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)

    def trigger_column_write(
        self,
        field_key: str,
        row_count: int,
        batch_num: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_COLUMN_WRITE)
            if not handler_pairs:
                return
            event = ColumnWriteEvent(field_key, row_count, batch_num)
            for hook, handler in handler_pairs:
                self._safe_call(hook, handler, event)


__all__ = [
    "BaseHook",
    "Hook",
    "HookManager",
    "IExecutionHook",
]
