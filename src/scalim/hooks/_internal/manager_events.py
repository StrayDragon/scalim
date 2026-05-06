import logging
from abc import ABC
from typing import Any, Callable, Dict, Hashable, List, Optional, Tuple, TypeVar

from ..._internal.loggingx import format_kv, prefix
from ..._internal.utils.loader_result import LOADER_RESULT_POLICY_VALUES, parse_loader_result_policy
from ...events import (
    Event,
    EventType,
)
from ...events._events import (
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
from .common import HOOK_RAISED_EXCEPTION_WARNING
from .manager_base import ExecutionHookLike, HookManagerBase, HookOnEventHandlerPair, HookTypedHandlerPair

_logger = logging.getLogger("scalim.hooks.base")
_EventT = TypeVar("_EventT")


class HookManagerEventMixin(HookManagerBase, ABC):
    def _safe_call(
        self,
        hook: ExecutionHookLike,
        method: Callable[[_EventT], Any],
        event: _EventT,
    ) -> None:
        if self._manager().debug_mode:
            method(event)
            return
        try:
            method(event)
        except Exception:  # noqa: BLE001
            _logger.warning(
                HOOK_RAISED_EXCEPTION_WARNING,
                type(hook).__name__,
                method.__name__,
                exc_info=True,
            )

    def _dispatch(
        self,
        handler_pairs: Optional[Tuple[Tuple[ExecutionHookLike, Callable[[_EventT], Any]], ...]],
        event: _EventT,
    ) -> None:
        if not handler_pairs:
            return
        self._manager().dispatch_strategy.dispatch(handler_pairs, event, self._safe_call)

    def _get_typed_handler_pairs(self, event_type: str) -> Optional[Tuple[HookTypedHandlerPair, ...]]:
        manager = self._manager()
        if not manager.has_hooks:
            return None
        with manager.lock:
            if not manager.hooks:
                manager.has_hooks = False
                return None
            return manager.typed_handlers_by_event_type.get(event_type)

    def _get_on_event_handler_pairs(self, event_type: str) -> Optional[Tuple[HookOnEventHandlerPair, ...]]:
        manager = self._manager()
        if not manager.has_hooks:
            return None
        with manager.lock:
            if not manager.hooks:
                manager.has_hooks = False
                return None
            return manager.on_event_handlers_by_event_type.get(event_type)

    def emit_typed(self, event_type: str, payload: Any) -> None:
        self._dispatch(self._get_typed_handler_pairs(event_type), payload)

    def emit_typed_policy(self, event_type: str, payload: Any) -> None:
        """发射类型化的策略决策 `signal`(默认 `fail-fast` 且保持确定性顺序).

        与纯观测事件不同,策略 `signal` 会影响运行时行为;默认必须 `fail-fast`(异常直接向外抛出).
        """
        handler_pairs = self._get_typed_handler_pairs(event_type)
        if not handler_pairs:
            return

        enter_hook = getattr(payload, "_enter_hook", None)  # pragma: allow-dynattr optional-interface: policy decision payload
        exit_hook = getattr(payload, "_exit_hook", None)  # pragma: allow-dynattr optional-interface: policy decision payload
        can_enter = callable(enter_hook)
        can_exit = callable(exit_hook)

        for hook, method in handler_pairs:
            if can_enter:
                _ = enter_hook(hook)
            try:
                method(payload)
            finally:
                if can_exit:
                    _ = exit_hook()

    def emit_on_event(self, event: Event) -> None:
        self._dispatch(self._get_on_event_handler_pairs(event.event_type), event)

    def trigger_pipeline_start(self, targets: List[str], batch_size: Optional[int]) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.PIPELINE_START)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, PipelineStartEvent(targets, batch_size))

    def trigger_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.PIPELINE_END)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, PipelineEndEvent(total_batches, total_duration))

    def trigger_batch_start(self, batch_num: int, row_ids: List[Any]) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.BATCH_START)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, BatchStartEvent(batch_num, row_ids))

    def trigger_batch_end(self, batch_num: int, duration: float) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.BATCH_END)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, BatchEndEvent(batch_num, duration))

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
        skipped_none_rows: Optional[int] = None,
    ) -> None:
        manager = self._manager()
        handler_pairs = self._get_typed_handler_pairs(EventType.LOADER_CALL)
        if handler_pairs is None:
            return

        payload: Any = result
        policy = manager.loader_result_policy
        if policy not in LOADER_RESULT_POLICY_VALUES:
            policy = parse_loader_result_policy(policy)
            manager.loader_result_policy = policy
        if policy == "none":
            payload = None
        elif policy == "summary":
            payload = self._summarize_result(result)
        elif policy == "sample":
            payload = self._sample_result(result)
        else:
            payload = result
        event = LoaderCallEvent(
            loader_name=loader_name,
            params=params,
            result=payload,
            duration=duration,
            batch_num=batch_num,
            cache_status=cache_status,
            cache_scope=cache_scope,
            lookup_key_count=lookup_key_count,
            skipped_none_rows=skipped_none_rows,
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
        handler_pairs = self._get_typed_handler_pairs(EventType.FIELD_COMPUTE)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, FieldComputeEvent(field_key, row_id, dependencies, result))

    def trigger_error(self, error: Exception, context: Dict[str, Any]) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.ERROR)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, ErrorEvent(error, context))

    def trigger_diagnostic_warning(
        self,
        message: str,
        source_id: Optional[str] = None,
        field_id: Optional[str] = None,
        lookup_key: Any = None,
        row_id: Any = None,
        *,
        sample_once: bool = False,
    ) -> None:
        manager = self._manager()
        handler_pairs: Optional[Tuple[HookTypedHandlerPair, ...]] = None
        with manager.lock:
            if sample_once and manager.diagnostic_warning_emitted:
                return
            if sample_once:
                manager.diagnostic_warning_emitted = True

            if manager.hooks:
                handler_pairs = manager.typed_handlers_by_event_type.get(EventType.DIAGNOSTIC_WARNING)
            else:
                manager.has_hooks = False

        if handler_pairs is not None:
            event = DiagnosticWarningEvent(
                message=message,
                source_id=source_id,
                field_id=field_id,
                lookup_key=lookup_key,
                row_id=row_id,
            )
            self._dispatch(handler_pairs, event)
            return

        if manager.fallback_logger_enabled:
            kv = format_kv(
                message=message,
                source_id=source_id,
                field_id=field_id,
                row_id=row_id,
                lookup_key=lookup_key,
            )
            _logger.warning("%s诊断警告 %s", prefix("pipeline"), kv)

    def trigger_field_slim(
        self,
        field_key: str,
        reason: str,
        *,
        batch_num: Optional[int] = None,
        remaining_fields: Optional[int] = None,
    ) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.FIELD_SLIM)
        if handler_pairs is None:
            return
        event = FieldSlimEvent(field_key=field_key, reason=reason, batch_num=batch_num, remaining_fields=remaining_fields)
        self._dispatch(handler_pairs, event)

    def trigger_row_write(
        self,
        row_id: Hashable,
        *,
        field_count: int,
        batch_num: Optional[int] = None,
        row_index: Optional[int] = None,
    ) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.ROW_WRITE)
        if handler_pairs is None:
            return
        event = RowWriteEvent(row_id=row_id, field_count=field_count, batch_num=batch_num, row_index=row_index)
        self._dispatch(handler_pairs, event)

    def trigger_row_release(
        self,
        row_id: Hashable,
        *,
        released_fields: List[str],
        retained_fields: List[str],
        batch_num: Optional[int] = None,
    ) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.ROW_RELEASE)
        if handler_pairs is None:
            return
        event = RowReleaseEvent(
            row_id=row_id,
            released_fields=released_fields,
            retained_fields=retained_fields,
            batch_num=batch_num,
        )
        self._dispatch(handler_pairs, event)

    def trigger_loader_slim(
        self,
        loader_name: str,
        original_keys: int,
        extracted_fields: List[str],
        batch_num: Optional[int] = None,
    ) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.LOADER_SLIM)
        if handler_pairs is None:
            return
        event = LoaderSlimEvent(
            loader_name=loader_name,
            original_keys=original_keys,
            extracted_fields=extracted_fields,
            batch_num=batch_num,
        )
        self._dispatch(handler_pairs, event)

    def trigger_column_write(
        self,
        field_key: str,
        row_count: int,
        batch_num: int,
    ) -> None:
        handler_pairs = self._get_typed_handler_pairs(EventType.COLUMN_WRITE)
        if handler_pairs is None:
            return
        self._dispatch(handler_pairs, ColumnWriteEvent(field_key, row_count, batch_num))


__all__ = ()
