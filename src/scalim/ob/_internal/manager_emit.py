import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Hashable, List, Optional, Tuple

from ..._internal.loggingx import format_kv, prefix
from ..._internal.utils.loader_result import LOADER_RESULT_POLICY_VALUES, LoaderResultPolicyValue, parse_loader_result_policy
from ...events import (
    WORKFLOW_ATTRIBUTION_META_KEYS,
    Event,
    EventType,
    now_ts,
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
    LoaderRetryEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from ...typedefs import RelationLookupResult
from ..observer import Observer
from .common import (
    CATALOG_EVENT_TYPES_SET,
    OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING,
    OBSERVER_RAISED_EXCEPTION_WARNING,
    ObserverManagerModeValue,
)

_logger = logging.getLogger(__name__)


class ObserverManagerEmitMixin(ABC):
    observers: Optional[List[Observer]] = None
    debug_mode: bool = False
    fallback_logger_enabled: bool = False
    loader_result_policy: LoaderResultPolicyValue = "full"
    run_id: str = ""
    mode: ObserverManagerModeValue = "process"
    _lock: "threading.RLock" = threading.RLock()
    _has_observers: bool = False
    _observers_by_event_type: Optional[Dict[str, Tuple[Observer, ...]]] = None
    _observers_for_unknown_event_type: Tuple[Observer, ...] = ()
    _diagnostic_warning_emitted: bool = False
    _seq: int = 0
    _event_meta_defaults: Optional[Dict[str, Any]] = None

    def _merge_event_meta_defaults(self, meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        defaults = self._event_meta_defaults
        if not defaults:
            return meta or {}
        if not meta:
            return dict(defaults)

        for key in WORKFLOW_ATTRIBUTION_META_KEYS:
            if key in defaults and key in meta:
                msg = "Event.meta key '{}' is reserved for workflow attribution and cannot be overridden.".format(key)
                raise ValueError(msg)

        merged = dict(defaults)
        merged.update(meta)
        return merged

    @abstractmethod
    def _record_event(self, event: Event) -> None: ...

    @abstractmethod
    def _supports_safely(self, observer: Observer, event_type: str) -> bool: ...

    @abstractmethod
    def _should_emit_event_type(self, event_type: str) -> bool: ...

    @abstractmethod
    def _summarize_result(self, result: Any) -> Dict[str, Any]: ...

    @abstractmethod
    def _sample_result(self, result: Any) -> Any: ...

    def _safe_call(
        self,
        observer: Observer,
        method: Callable[[Event], None],
        event: Event,
    ) -> None:
        try:
            method(event)
        except Exception:
            if self.debug_mode:
                raise
            _logger.warning(
                OBSERVER_RAISED_EXCEPTION_WARNING,
                type(observer).__name__,
                method.__name__,
                exc_info=True,
            )

    def _close_observer_safely(self, observer: Observer) -> None:
        try:
            observer.close()
        except Exception:
            if self.debug_mode:
                raise
            _logger.warning(
                OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING,
                type(observer).__name__,
                exc_info=True,
            )

    def _next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def emit(self, event: Event) -> None:
        if self.mode == "capture":
            self._record_event(event)
            return
        event_type = event.event_type

        observers: Tuple[Observer, ...] = ()
        unknown_observers: Tuple[Observer, ...] = ()
        with self._lock:
            if not self._has_observers:
                return
            if event_type in CATALOG_EVENT_TYPES_SET:
                observers_by_event_type = self._observers_by_event_type
                if observers_by_event_type is None:
                    observers_by_event_type = {}
                    self._observers_by_event_type = observers_by_event_type
                observers = observers_by_event_type.get(event_type, ())
            else:
                unknown_observers = self._observers_for_unknown_event_type

        if observers:
            for observer in observers:
                self._safe_call(observer, observer.on_event, event)
            return

        if not unknown_observers:
            return
        for observer in unknown_observers:
            if not self._supports_safely(observer, event_type):
                continue
            self._safe_call(observer, observer.on_event, event)

    def emit_event(self, event_type: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> Event:
        merged_meta = self._merge_event_meta_defaults(meta)
        event = Event(
            event_type=event_type,
            timestamp=now_ts(),
            run_id=self.run_id,
            payload=payload,
            meta=merged_meta,
            seq=self._next_seq(),
        )
        self.emit(event)
        return event

    def close(self) -> None:
        with self._lock:
            observers = self.observers
            if observers is None:
                observers = []
                self.observers = observers
            for observer in observers:
                self._close_observer_safely(observer)

    def emit_pipeline_start(self, targets: List[str], batch_size: Optional[int]) -> None:
        if not self._should_emit_event_type(EventType.PIPELINE_START):
            return
        payload = PipelineStartEvent(targets, batch_size)
        _ = self.emit_event(EventType.PIPELINE_START, payload)

    def emit_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        if not self._should_emit_event_type(EventType.PIPELINE_END):
            return
        payload = PipelineEndEvent(total_batches, total_duration)
        _ = self.emit_event(EventType.PIPELINE_END, payload)

    def emit_batch_start(self, batch_num: int, row_ids: List[Any]) -> None:
        if not self._should_emit_event_type(EventType.BATCH_START):
            return
        payload = BatchStartEvent(batch_num, row_ids)
        _ = self.emit_event(EventType.BATCH_START, payload)

    def emit_batch_end(self, batch_num: int, duration: float) -> None:
        if not self._should_emit_event_type(EventType.BATCH_END):
            return
        payload = BatchEndEvent(batch_num, duration)
        _ = self.emit_event(EventType.BATCH_END, payload)

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
    ) -> None:
        if not self._should_emit_event_type(EventType.LOADER_CALL):
            return
        payload = result
        policy = self.loader_result_policy
        if policy not in LOADER_RESULT_POLICY_VALUES:
            policy = parse_loader_result_policy(policy)
            self.loader_result_policy = policy
        if policy == "none":
            payload = None
        elif policy == "summary":
            payload = self._summarize_result(result)
        elif policy == "sample":
            payload = self._sample_result(result)
        else:
            payload = result
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
        _ = self.emit_event(EventType.LOADER_CALL, event_payload)

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
    ) -> None:
        if not self._should_emit_event_type(EventType.LOADER_RETRY):
            return
        payload = LoaderRetryEvent(
            loader_name=loader_name,
            callsite=callsite,
            attempt_num=int(attempt_num),
            max_attempts=int(max_attempts),
            elapsed_seconds=float(elapsed_seconds),
            sleep_seconds=float(sleep_seconds),
            error_type=str(error_type),
            error_message=error_message,
            batch_num=batch_num,
        )
        _ = self.emit_event(EventType.LOADER_RETRY, payload)

    def emit_field_compute(
        self,
        field_key: str,
        row_id: Hashable,
        dependencies: Dict[str, Any],
        result: Any,
    ) -> None:
        if not self._should_emit_event_type(EventType.FIELD_COMPUTE):
            return
        payload = FieldComputeEvent(field_key, row_id, dependencies, result)
        _ = self.emit_event(EventType.FIELD_COMPUTE, payload)

    def emit_error(self, error: Exception, context: Dict[str, Any]) -> None:
        if not self._should_emit_event_type(EventType.ERROR):
            return
        payload = ErrorEvent(error, context)
        _ = self.emit_event(EventType.ERROR, payload)

    def emit_diagnostic_warning(
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

        if self._should_emit_event_type(EventType.DIAGNOSTIC_WARNING):
            payload = DiagnosticWarningEvent(
                message=message,
                source_id=source_id,
                field_id=field_id,
                lookup_key=lookup_key,
                row_id=row_id,
            )
            _ = self.emit_event(EventType.DIAGNOSTIC_WARNING, payload)
        elif self.fallback_logger_enabled:
            kv = format_kv(
                message=message,
                source_id=source_id,
                field_id=field_id,
                row_id=row_id,
                lookup_key=lookup_key,
            )
            _logger.warning("%s诊断警告 %s", prefix("pipeline"), kv)

    def emit_field_slim(
        self,
        field_key: str,
        reason: str,
        batch_num: int,
        remaining_fields: int,
    ) -> None:
        if not self._should_emit_event_type(EventType.FIELD_SLIM):
            return
        payload = FieldSlimEvent(field_key, reason, batch_num, remaining_fields)
        _ = self.emit_event(EventType.FIELD_SLIM, payload)

    def emit_row_write(
        self,
        row_id: Hashable,
        field_count: int,
        batch_num: int,
        row_index: int,
    ) -> None:
        if not self._should_emit_event_type(EventType.ROW_WRITE):
            return
        payload = RowWriteEvent(row_id, field_count, batch_num, row_index)
        _ = self.emit_event(EventType.ROW_WRITE, payload)

    def emit_row_release(
        self,
        row_id: Hashable,
        released_fields: List[str],
        retained_fields: List[str],
        batch_num: int,
    ) -> None:
        if not self._should_emit_event_type(EventType.ROW_RELEASE):
            return
        payload = RowReleaseEvent(row_id, released_fields, retained_fields, batch_num)
        _ = self.emit_event(EventType.ROW_RELEASE, payload)

    def emit_loader_slim(
        self,
        loader_name: str,
        original_keys: int,
        extracted_fields: List[str],
        batch_num: int,
    ) -> None:
        if not self._should_emit_event_type(EventType.LOADER_SLIM):
            return
        payload = LoaderSlimEvent(loader_name, original_keys, extracted_fields, batch_num)
        _ = self.emit_event(EventType.LOADER_SLIM, payload)

    def emit_column_write(
        self,
        field_key: str,
        row_count: int,
        batch_num: int,
    ) -> None:
        if not self._should_emit_event_type(EventType.COLUMN_WRITE):
            return
        payload = ColumnWriteEvent(field_key, row_count, batch_num)
        _ = self.emit_event(EventType.COLUMN_WRITE, payload)

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
    ) -> None:
        if not self._should_emit_event_type(EventType.RELATION_LOOKUP):
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
        _ = self.emit_event(EventType.RELATION_LOOKUP, payload)

    def emit_stage_span(self, stage: str, batch_num: int, duration: float) -> None:
        if not self._should_emit_event_type(EventType.STAGE_SPAN):
            return
        payload = StageSpanEvent(stage=stage, batch_num=batch_num, duration=duration)
        _ = self.emit_event(EventType.STAGE_SPAN, payload)


__all__ = ()
