# region imports

import threading
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

from ..events.catalog import (
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
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from ..hooks.base import HookManager, IExecutionHook
from ..typedefs import RelationLookupResult
from .components import split_components
from .manager import ObserverManager
from .observer import Observer

# endregion

_PayloadT = TypeVar("_PayloadT")


class InstrumentationHub:
    """Unified instrumentation hub for hooks + observers.

    Execution hotpaths SHOULD call hub once, and use `wants(event_type)` to gate any heavy payload preparation.
    """

    hook_manager: HookManager
    observer_manager: ObserverManager
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool

    def __init__(
        self,
        hook_manager: HookManager | None = None,
        observer_manager: ObserverManager | None = None,
    ) -> None:
        self.hook_manager = hook_manager or HookManager()
        self.observer_manager = observer_manager or ObserverManager()
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False

    def __getstate__(self) -> dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()
        if not hasattr(self, "_diagnostic_warning_emitted"):
            self._diagnostic_warning_emitted = False

    def register(self, subscriber: Observer | IExecutionHook) -> None:
        observers, hooks = split_components([subscriber])
        if observers:
            self.observer_manager.register(observers[0])
            return
        self.hook_manager.register(hooks[0])

    def unregister(self, subscriber: Observer | IExecutionHook) -> bool:
        observers, hooks = split_components([subscriber])
        if observers:
            return self.observer_manager.unregister(observers[0])
        return self.hook_manager.unregister(hooks[0])

    def clear(self) -> None:
        self.hook_manager.clear()
        self.observer_manager.clear()

    def wants(self, event_type: str) -> bool:
        # O(1) wants check; used by hotpaths to avoid building payloads/kwargs when nothing is subscribed.
        return self.hook_manager.wants(event_type) or self.observer_manager.wants(event_type)

    def _emit_assume_wanted(
        self,
        event_type: str,
        payload: Any,
        meta: dict[str, Any] | None = None,
    ) -> Event | None:
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
        meta: dict[str, Any] | None = None,
    ) -> Event | None:
        if not self.wants(event_type):
            return None
        payload = payload_factory()
        return self._emit_assume_wanted(event_type, payload, meta=meta)

    def emit(
        self,
        event_type: str,
        payload: Any,
        meta: dict[str, Any] | None = None,
    ) -> Event | None:
        """Emit an event to typed hooks, observers, and `hook.on_event(Event)` subscribers.

        Returns the built `Event` envelope when emitted to observer/on_event paths; otherwise returns None.
        """
        if not self.wants(event_type):
            return None
        return self._emit_assume_wanted(event_type, payload, meta=meta)

    def emit_recorded_event(self, event: Event) -> None:
        """Replay a previously recorded event (e.g. from parallel capture mode)."""
        self.observer_manager.emit(event)
        if self.observer_manager.mode != "capture":
            self.hook_manager.emit_on_event(event)

    # ---- typed helpers (preferred in execution hotpaths) ----

    def emit_pipeline_start(self, targets: list[str], batch_size: int) -> None:
        if not self.wants(EVENT_PIPELINE_START):
            return
        _ = self._emit_assume_wanted(EVENT_PIPELINE_START, PipelineStartEvent(targets, batch_size))

    def emit_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        if not self.wants(EVENT_PIPELINE_END):
            return
        _ = self._emit_assume_wanted(EVENT_PIPELINE_END, PipelineEndEvent(total_batches, total_duration))

    def emit_batch_start(self, batch_num: int, row_ids: list[Any]) -> None:
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
        params: dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: int | None = None,
        cache_status: str | None = None,
        cache_scope: str | None = None,
        lookup_key_count: int | None = None,
        field_keys: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        # Typed hooks may have a different loader_result_policy than the observer/event path.
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

    def emit_field_compute(
        self,
        field_key: str,
        row_id: Hashable,
        dependencies: dict[str, Any],
        result: Any,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not self.wants(EVENT_FIELD_COMPUTE):
            return
        _ = self._emit_assume_wanted(EVENT_FIELD_COMPUTE, FieldComputeEvent(field_key, row_id, dependencies, result), meta=meta)

    def emit_error(self, error: Exception, context: dict[str, Any], meta: dict[str, Any] | None = None) -> None:
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
        meta: dict[str, Any] | None = None,
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
                # Use ObserverManager logger for consistency.
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
        meta: dict[str, Any] | None = None,
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
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not self.wants(EVENT_ROW_WRITE):
            return
        _ = self._emit_assume_wanted(EVENT_ROW_WRITE, RowWriteEvent(row_id, field_count, batch_num, row_index), meta=meta)

    def emit_row_release(
        self,
        row_id: Hashable,
        released_fields: list[str],
        retained_fields: list[str],
        batch_num: int,
        meta: dict[str, Any] | None = None,
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
        extracted_fields: list[str],
        batch_num: int,
        meta: dict[str, Any] | None = None,
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
        meta: dict[str, Any] | None = None,
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
        fk_type: str | None = None,
        expected_type: str | None = None,
        error_message: str | None = None,
        meta: dict[str, Any] | None = None,
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

    def emit_stage_span(self, stage: str, batch_num: int, duration: float, meta: dict[str, Any] | None = None) -> None:
        if not self.wants(EVENT_STAGE_SPAN):
            return
        _ = self._emit_assume_wanted(EVENT_STAGE_SPAN, StageSpanEvent(stage=stage, batch_num=batch_num, duration=duration), meta=meta)


__all__ = [
    "InstrumentationHub",
]
