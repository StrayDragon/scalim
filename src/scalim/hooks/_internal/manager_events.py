# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
import logging
from typing import Any, Callable, Dict, Hashable, List, Optional, Tuple, TypeVar

from ...events.catalog import (
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_COLUMN_WRITE,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_ERROR,
    EVENT_FIELD_COMPUTE,
    EVENT_FIELD_SLIM,
    EVENT_LOADER_CALL,
    EVENT_LOADER_SLIM,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_ROW_RELEASE,
    EVENT_ROW_WRITE,
)
from ...events.event import Event
from ...events.events import (
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

_logger = logging.getLogger("scalim.hooks.base")
_EventT = TypeVar("_EventT")


class HookManagerEventMixin:
    def _safe_call(
        self,
        hook: Any,
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
        handler_pairs: Optional[Tuple[Tuple[Any, Callable[[Any], Any]], ...]],
        event: Any,
    ) -> None:
        if not handler_pairs:
            return
        self._dispatch_strategy.dispatch(handler_pairs, event, self._safe_call)

    def emit_typed(self, event_type: str, payload: Any) -> None:
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
        source_id: Optional[str] = None,
        field_id: Optional[str] = None,
        lookup_key: Any = None,
        row_id: Any = None,
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
        *,
        batch_num: Optional[int] = None,
        remaining_fields: Optional[int] = None,
    ) -> None:
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_FIELD_SLIM)
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
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ROW_WRITE)
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
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_ROW_RELEASE)
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
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_LOADER_SLIM)
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
        if not self._has_hooks:
            return
        with self._lock:
            if not self.hooks:
                self._has_hooks = False
                return
            handler_pairs = self._typed_handlers_by_event_type.get(EVENT_COLUMN_WRITE)
            event = ColumnWriteEvent(field_key, row_count, batch_num)
            self._dispatch(handler_pairs, event)
