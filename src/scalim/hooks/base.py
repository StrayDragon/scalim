# region imports

import contextlib
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, Callable, Dict, Hashable, List, Mapping, Optional, Sequence, Set, Tuple, TypeVar, cast

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
from .dispatch import HookDispatchStrategy

# endregion

_logger = logging.getLogger(__name__)
_EventT = TypeVar("_EventT")
_TypedHandlerPair = Tuple["IExecutionHook", Callable[[Any], Any]]
_OnEventHandlerPair = Tuple["IExecutionHook", Callable[[Event], Any]]

HOOK_RAISED_EXCEPTION_WARNING = "钩子 %s.%s 抛出异常"

_HOOK_TYPED_DISPATCH_MAP: Dict[str, str] = {
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

_CATALOG_EVENT_TYPES: Tuple[str, ...] = (
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


def _resolve_mro_attr(cls: type, name: str) -> Any:
    for mro_cls in cls.__mro__:
        cls_dict = mro_cls.__dict__
        if name in cls_dict:
            return cls_dict[name]
    return None


def _read_optional_attr(obj: Any, name: str) -> Any:
    try:
        return obj.__getattribute__(name)
    except AttributeError:
        return None


def _read_callable_attr(obj: Any, name: str) -> Optional[Callable[..., Any]]:
    value = _read_optional_attr(obj, name)
    if value is None or not callable(value):
        return None
    return cast("Callable[..., Any]", value)


def _validate_event_types(hook: Any, value: Any) -> Optional[Set[str]]:
    if value is None:
        return None
    if not isinstance(value, AbstractSet):
        msg = "hook.event_types must be None or Set[str]; got {} for {}".format(type(value).__name__, type(hook).__name__)
        raise TypeError(msg)
    for item in value:
        if not isinstance(item, str):
            msg = "hook.event_types must contain only str; got {} element {!r} for {}".format(
                type(item).__name__, item, type(hook).__name__
            )
            raise TypeError(msg)
    return cast("Set[str]", value)


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


class HookManager:
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
        self.debug_mode = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = self._normalize_loader_result_policy(loader_result_policy)
        self.loader_result_sample_size = max(1, loader_result_sample_size)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False
        self._dispatch_strategy = dispatch_strategy or HookDispatchStrategy()

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

    def _hook_overrides_on_event(self, hook: IExecutionHook) -> bool:
        on_event_attr = _resolve_mro_attr(type(hook), "on_event")
        if on_event_attr is None:
            return False
        return on_event_attr is not BaseHook.__dict__.get("on_event")

    def _iter_hook_typed_subscriptions(self, hook: IExecutionHook) -> "Tuple[str, ...]":
        hook_type = type(hook)
        subscribed: List[str] = []
        for event_type, handler_name in _HOOK_TYPED_DISPATCH_MAP.items():
            hook_handler = _resolve_mro_attr(hook_type, handler_name)
            if hook_handler is None:
                continue
            base_handler = BaseHook.__dict__.get(handler_name)
            # 若该钩子继承了 `BaseHook` 的空操作处理函数,则不订阅该事件.
            if base_handler is not None and hook_handler is base_handler:
                continue
            subscribed.append(event_type)
        return tuple(subscribed)

    def _append_hook_typed_handlers(
        self,
        hook: IExecutionHook,
        event_types: Optional[Set[str]],
        typed_handlers_by_type: "Dict[str, List[_TypedHandlerPair]]",
    ) -> None:
        if event_types is None:
            for event_type in self._iter_hook_typed_subscriptions(hook):
                handler_name = _HOOK_TYPED_DISPATCH_MAP[event_type]
                handler = _read_callable_attr(hook, handler_name)
                if handler is None:
                    continue
                typed_handlers_by_type[event_type].append((hook, handler))
            return

        for event_type in self._iter_hook_typed_subscriptions(hook):
            if event_type not in event_types:
                continue
            handler_name = _HOOK_TYPED_DISPATCH_MAP[event_type]
            handler = _read_callable_attr(hook, handler_name)
            if handler is None:
                continue
            typed_handlers_by_type[event_type].append((hook, handler))

    def _append_hook_on_event_handlers(
        self,
        hook: IExecutionHook,
        event_types: Optional[Set[str]],
        on_event_handlers_by_type: "Dict[str, List[_OnEventHandlerPair]]",
    ) -> None:
        if not self._hook_overrides_on_event(hook):
            return
        on_event_handler = _read_callable_attr(hook, "on_event")
        if on_event_handler is None:
            return
        if event_types is None:
            for event_type in _CATALOG_EVENT_TYPES:
                on_event_handlers_by_type[event_type].append((hook, on_event_handler))
            return
        for event_type in event_types:
            if event_type in on_event_handlers_by_type:
                on_event_handlers_by_type[event_type].append((hook, on_event_handler))

    def _rebuild_subscription_cache(self) -> None:
        typed_handlers_by_type: Dict[str, List[_TypedHandlerPair]] = {event_type: [] for event_type in _HOOK_TYPED_DISPATCH_MAP}
        on_event_handlers_by_type: Dict[str, List[_OnEventHandlerPair]] = {event_type: [] for event_type in _CATALOG_EVENT_TYPES}

        for hook in self.hooks:
            event_types = _validate_event_types(hook, _read_optional_attr(hook, "event_types"))
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
                HOOK_RAISED_EXCEPTION_WARNING,
                type(hook).__name__,
                method.__name__,
                exc_info=True,
            )

    def _dispatch(
        self,
        handler_pairs: Optional[Tuple[Tuple["IExecutionHook", Callable[[Any], Any]], ...]],
        event: Any,
    ) -> None:
        if not handler_pairs:
            return
        self._dispatch_strategy.dispatch(handler_pairs, event, self._safe_call)

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
            _ = _validate_event_types(hook, _read_optional_attr(hook, "event_types"))
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
        """按 `event_type` → 处理函数 的映射触发类型化钩子回调.

        注意: 此方法不会构造 `payload`,只在 `payload` 已就绪时负责分发.
        """
        if not self._has_hooks:
            return
        with self._lock:
            handler_pairs = self._typed_handlers_by_event_type.get(event_type)
        self._dispatch(handler_pairs, payload)

    def emit_on_event(self, event: Event) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            handler_pairs = self._on_event_handlers_by_event_type.get(event.event_type)
        self._dispatch(handler_pairs, event)

    def trigger_pipeline_start(self, targets: List[str], batch_size: Optional[int]) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_PIPELINE_START)
            event = PipelineStartEvent(targets, batch_size)
            self._dispatch(handler_pairs, event)

    def trigger_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_PIPELINE_END)
            event = PipelineEndEvent(total_batches, total_duration)
            self._dispatch(handler_pairs, event)

    def trigger_batch_start(self, batch_num: int, row_ids: List[Any]) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_BATCH_START)
            event = BatchStartEvent(batch_num, row_ids)
            self._dispatch(handler_pairs, event)

    def trigger_batch_end(self, batch_num: int, duration: float) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_BATCH_END)
            event = BatchEndEvent(batch_num, duration)
            self._dispatch(handler_pairs, event)

    def trigger_loader_call(
        self,
        loader_name: str,
        params: Dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: Optional[int] = None,
        cache_status: Optional[str] = None,
        cache_scope: Optional[str] = None,
        lookup_key_count: Optional[int] = None,
        field_keys: Optional[List[str]] = None,
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
            self._dispatch(handler_pairs, event)

    def trigger_field_compute(
        self,
        field_key: str,
        row_id: Hashable,
        dependencies: Dict[str, Any],
        result: Any,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_FIELD_COMPUTE)
            event = FieldComputeEvent(field_key, row_id, dependencies, result)
            self._dispatch(handler_pairs, event)

    def trigger_error(self, error: Exception, context: Dict[str, Any]) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ERROR)
            event = ErrorEvent(error, context)
            self._dispatch(handler_pairs, event)

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
                self._dispatch(handler_pairs, event)
                return

            self._has_hooks = False

        if self.fallback_logger_enabled:
            _logger.warning(
                "[诊断] %s | 源=%s 字段=%s 行标识=%s 查找键=%r",
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
            event = FieldSlimEvent(field_key, reason, batch_num, remaining_fields)
            self._dispatch(handler_pairs, event)

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
            event = RowWriteEvent(row_id, field_count, batch_num, row_index)
            self._dispatch(handler_pairs, event)

    def trigger_row_release(
        self,
        row_id: Hashable,
        released_fields: List[str],
        retained_fields: List[str],
        batch_num: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ROW_RELEASE)
            event = RowReleaseEvent(row_id, released_fields, retained_fields, batch_num)
            self._dispatch(handler_pairs, event)

    def trigger_loader_slim(
        self,
        loader_name: str,
        original_keys: int,
        extracted_fields: List[str],
        batch_num: int,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_LOADER_SLIM)
            event = LoaderSlimEvent(loader_name, original_keys, extracted_fields, batch_num)
            self._dispatch(handler_pairs, event)

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
            event = ColumnWriteEvent(field_key, row_count, batch_num)
            self._dispatch(handler_pairs, event)


__all__ = [
    "BaseHook",
    "Hook",
    "HookManager",
    "IExecutionHook",
]
