# region imports

import threading
from typing import Any, Callable, Dict, Hashable, List, Optional, TypeVar, Union

from ..events import (
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
    Event,
)
from ..events._events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderRetryEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from ..hooks import HookManager, IExecutionHook
from ..typedefs import RelationLookupResult
from .components import split_components
from .manager import ObserverManager
from .observer import Observer

# endregion

_PayloadT = TypeVar("_PayloadT")


class InstrumentationHub:
    """统一的观测枢纽: 负责钩子与观测器.

    执行热路径应尽量只调用一次该枢纽,并使用 `wants(event_type)` 来门控昂贵的载荷构造.
    """

    hook_manager: HookManager
    observer_manager: ObserverManager
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool

    def __init__(
        self,
        hook_manager: Optional[HookManager] = None,
        observer_manager: Optional[ObserverManager] = None,
    ) -> None:
        self.hook_manager = hook_manager or HookManager()
        self.observer_manager = observer_manager or ObserverManager()
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False

    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = bool(state.get("_diagnostic_warning_emitted", False))

    def register(self, subscriber: Union[Observer, IExecutionHook]) -> None:
        observers, hooks = split_components([subscriber])
        if observers:
            self.observer_manager.register(observers[0])
            return
        self.hook_manager.register(hooks[0])

    def unregister(self, subscriber: Union[Observer, IExecutionHook]) -> bool:
        observers, hooks = split_components([subscriber])
        if observers:
            return self.observer_manager.unregister(observers[0])
        return self.hook_manager.unregister(hooks[0])

    def clear(self) -> None:
        self.hook_manager.clear()
        self.observer_manager.clear()

    def wants(self, event_type: str) -> bool:
        # `wants` 为 O(1) 检查;用于热路径在无人订阅时避免构造载荷/关键字参数.
        return self.hook_manager.wants(event_type) or self.observer_manager.wants(event_type)

    def _emit_assume_wanted(
        self,
        event_type: str,
        payload: Any,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Event]:
        self.hook_manager.emit_typed(event_type, payload)

        if not (self.observer_manager.wants(event_type) or self.hook_manager.wants_on_event(event_type)):
            return None

        event = self.observer_manager.emit_event(event_type, payload, meta=meta)
        if self.observer_manager.mode != "capture":
            self.hook_manager.emit_on_event(event)
        return event

    def emit_lazy(
        self,
        event_type: str,
        payload_factory: Callable[[], _PayloadT],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Event]:
        if not self.wants(event_type):
            return None
        payload = payload_factory()
        return self._emit_assume_wanted(event_type, payload, meta=meta)

    def emit(
        self,
        event_type: str,
        payload: Any,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Event]:
        """向类型化钩子、观测器以及订阅了 `hook.on_event(Event)` 的监听方发送事件.

        当事件会被发送到观测器/`on_event` 路径时,返回构建好的 `Event` 包装;否则返回 `None`.
        """
        if not self.wants(event_type):
            return None
        return self._emit_assume_wanted(event_type, payload, meta=meta)

    def emit_recorded_event(self, event: Event) -> None:
        """回放此前记录的事件(例如来自并行捕获模式)."""
        self.observer_manager.emit(event)
        if self.observer_manager.mode != "capture":
            self.hook_manager.emit_on_event(event)

    # ---- 类型化辅助方法(执行热路径优先使用) ----

    def emit_pipeline_start(self, targets: List[str], batch_size: Optional[int]) -> None:
        if not self.wants(EVENT_PIPELINE_START):
            return
        _ = self._emit_assume_wanted(EVENT_PIPELINE_START, PipelineStartEvent(targets, batch_size))

    def emit_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        if not self.wants(EVENT_PIPELINE_END):
            return
        _ = self._emit_assume_wanted(EVENT_PIPELINE_END, PipelineEndEvent(total_batches, total_duration))

    def emit_batch_start(self, batch_num: int, row_ids: List[Any]) -> None:
        if not self.wants(EVENT_BATCH_START):
            return
        _ = self._emit_assume_wanted(EVENT_BATCH_START, BatchStartEvent(batch_num, row_ids))

    def emit_batch_end(self, batch_num: int, duration: float) -> None:
        if not self.wants(EVENT_BATCH_END):
            return
        _ = self._emit_assume_wanted(EVENT_BATCH_END, BatchEndEvent(batch_num, duration))

    def emit_loader_call(
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
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        # 类型化钩子的 `loader_result_policy` 可能与观测器/事件路径不同.
        if self.hook_manager.wants_typed(EVENT_LOADER_CALL):
            self.hook_manager.trigger_loader_call(
                loader_name=loader_name,
                params=params,
                result=result,
                duration=duration,
                batch_num=batch_num,
                cache_status=cache_status,
                cache_scope=cache_scope,
                lookup_key_count=lookup_key_count,
                field_keys=field_keys,
            )

        if not (self.observer_manager.wants(EVENT_LOADER_CALL) or self.hook_manager.wants_on_event(EVENT_LOADER_CALL)):
            return

        payload = result
        if self.observer_manager.loader_result_policy != "full":
            if self.observer_manager.loader_result_policy == "none":
                payload = None
            elif self.observer_manager.loader_result_policy == "summary":
                payload = self.observer_manager.summarize_result(result)
            elif self.observer_manager.loader_result_policy == "sample":
                payload = self.observer_manager.sample_result(result)

        event_payload = LoaderCallEvent(
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
        event = self.observer_manager.emit_event(EVENT_LOADER_CALL, event_payload, meta=meta)
        if self.observer_manager.mode != "capture":
            self.hook_manager.emit_on_event(event)

    def emit_loader_retry(
        self,
        *,
        loader_name: str,
        callsite: str,
        attempt_num: int,
        max_attempts: int,
        elapsed_seconds: float,
        sleep_seconds: float,
        error_type: str,
        error_message: Optional[str],
        batch_num: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_LOADER_RETRY):
            return
        _ = self._emit_assume_wanted(
            EVENT_LOADER_RETRY,
            LoaderRetryEvent(
                loader_name=loader_name,
                callsite=callsite,
                attempt_num=int(attempt_num),
                max_attempts=int(max_attempts),
                elapsed_seconds=float(elapsed_seconds),
                sleep_seconds=float(sleep_seconds),
                error_type=str(error_type),
                error_message=error_message,
                batch_num=batch_num,
            ),
            meta=meta,
        )

    def emit_field_compute(
        self,
        field_key: str,
        row_id: Hashable,
        dependencies: Dict[str, Any],
        result: Any,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_FIELD_COMPUTE):
            return
        _ = self._emit_assume_wanted(EVENT_FIELD_COMPUTE, FieldComputeEvent(field_key, row_id, dependencies, result), meta=meta)

    def emit_error(self, error: Exception, context: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        if not self.wants(EVENT_ERROR):
            return
        _ = self._emit_assume_wanted(EVENT_ERROR, ErrorEvent(error, context), meta=meta)

    def emit_diagnostic_warning(
        self,
        message: str,
        source_id: str,
        field_id: str,
        lookup_key: Any,
        row_id: Hashable,
        *,
        sample_once: bool = False,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if sample_once:
            with self._lock:
                if self._diagnostic_warning_emitted:
                    return
                self._diagnostic_warning_emitted = True

        hooks_want = self.hook_manager.wants_typed(EVENT_DIAGNOSTIC_WARNING)
        event_want = self.observer_manager.wants(EVENT_DIAGNOSTIC_WARNING) or self.hook_manager.wants_on_event(EVENT_DIAGNOSTIC_WARNING)

        if not hooks_want and not event_want:
            if self.hook_manager.fallback_logger_enabled or self.observer_manager.fallback_logger_enabled:
                # 为保持一致性,这里使用 `ObserverManager` 的日志记录器.
                self.observer_manager.emit_diagnostic_warning(
                    message=message,
                    source_id=source_id,
                    field_id=field_id,
                    lookup_key=lookup_key,
                    row_id=row_id,
                    sample_once=False,
                )
            return

        payload = DiagnosticWarningEvent(
            message=message,
            source_id=source_id,
            field_id=field_id,
            lookup_key=lookup_key,
            row_id=row_id,
        )

        if hooks_want:
            self.hook_manager.emit_typed(EVENT_DIAGNOSTIC_WARNING, payload)

        if not event_want:
            return

        event = self.observer_manager.emit_event(EVENT_DIAGNOSTIC_WARNING, payload, meta=meta)
        if self.observer_manager.mode != "capture":
            self.hook_manager.emit_on_event(event)

    def emit_field_slim(
        self,
        field_key: str,
        reason: str,
        batch_num: int,
        remaining_fields: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_FIELD_SLIM):
            return
        _ = self._emit_assume_wanted(
            EVENT_FIELD_SLIM,
            FieldSlimEvent(field_key, reason, batch_num, remaining_fields),
            meta=meta,
        )

    def emit_row_write(
        self,
        row_id: Hashable,
        field_count: int,
        batch_num: int,
        row_index: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_ROW_WRITE):
            return
        _ = self._emit_assume_wanted(EVENT_ROW_WRITE, RowWriteEvent(row_id, field_count, batch_num, row_index), meta=meta)

    def emit_row_release(
        self,
        row_id: Hashable,
        released_fields: List[str],
        retained_fields: List[str],
        batch_num: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_ROW_RELEASE):
            return
        _ = self._emit_assume_wanted(
            EVENT_ROW_RELEASE,
            RowReleaseEvent(row_id, released_fields, retained_fields, batch_num),
            meta=meta,
        )

    def emit_loader_slim(
        self,
        loader_name: str,
        original_keys: int,
        extracted_fields: List[str],
        batch_num: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_LOADER_SLIM):
            return
        _ = self._emit_assume_wanted(
            EVENT_LOADER_SLIM,
            LoaderSlimEvent(loader_name, original_keys, extracted_fields, batch_num),
            meta=meta,
        )

    def emit_column_write(
        self,
        field_key: str,
        row_count: int,
        batch_num: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_COLUMN_WRITE):
            return
        _ = self._emit_assume_wanted(EVENT_COLUMN_WRITE, ColumnWriteEvent(field_key, row_count, batch_num), meta=meta)

    def emit_relation_lookup(
        self,
        field_key: str,
        row_id: Hashable,
        fk_raw: Any,
        fk_normalized: Any,
        target_source: str,
        result: RelationLookupResult,
        fk_type: Optional[str] = None,
        expected_type: Optional[str] = None,
        error_message: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.wants(EVENT_RELATION_LOOKUP):
            return
        payload = RelationLookupEvent(
            field_key=field_key,
            row_id=row_id,
            fk_raw=fk_raw,
            fk_normalized=fk_normalized,
            target_source=target_source,
            result=result,
            fk_type=fk_type,
            expected_type=expected_type,
            error_message=error_message,
        )
        _ = self._emit_assume_wanted(EVENT_RELATION_LOOKUP, payload, meta=meta)

    def emit_stage_span(self, stage: str, batch_num: int, duration: float, meta: Optional[Dict[str, Any]] = None) -> None:
        if not self.wants(EVENT_STAGE_SPAN):
            return
        _ = self._emit_assume_wanted(EVENT_STAGE_SPAN, StageSpanEvent(stage=stage, batch_num=batch_num, duration=duration), meta=meta)


__all__ = [
    "InstrumentationHub",
]
