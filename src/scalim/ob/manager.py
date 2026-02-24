# region imports

import contextlib
import logging
import threading
from collections import deque
from collections.abc import Callable, Hashable, Mapping, Sequence
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, cast

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
from ..events.event import Event, generate_run_id, now_ts
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
from ..typedefs import RelationLookupResult
from .observer import EventDispatchObserver, Observer

# endregion

_logger = logging.getLogger(__name__)

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

_CATALOG_EVENT_TYPES_SET: set[str] = set(_CATALOG_EVENT_TYPES)

_DEFAULT_MAX_RECORDED_EVENTS = 10_000
_CAPTURE_OVERFLOW_POLICIES = ("raise", "drop-oldest", "drop-newest")


class ObserverCaptureOverflowError(RuntimeError):
    pass


class ObserverManager:
    """Observer manager - register observers and dispatch events.

    Note: manage observers via register/unregister/clear; direct mutation of the observers list can desync subscription caches.
    """

    observers: list[Observer]
    _has_observers: bool
    _supports_all: bool
    _supported_event_types: set[str]
    _observers_by_event_type: dict[str, tuple[Observer, ...]]
    _observers_for_unknown_event_type: tuple[Observer, ...]
    _capture_event_types: set[str] | None
    _capture_unknown_event_types: bool
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: str
    loader_result_sample_size: int
    run_id: str
    mode: str
    max_recorded_events: int | None
    capture_overflow_policy: str
    _lock: "threading.RLock"
    _diagnostic_warning_emitted: bool
    _seq: int
    _recorded_events: deque[Event]

    def __init__(
        self,
        observers: list[Observer] | None = None,
        *,
        enable_debugging: bool = False,
        fallback_logger_enabled: bool = False,
        loader_result_policy: str = "full",
        loader_result_sample_size: int = 5,
        run_id: str | None = None,
        mode: str = "process",
        max_recorded_events: int | None = _DEFAULT_MAX_RECORDED_EVENTS,
        capture_overflow_policy: str = "raise",
    ) -> None:
        self.observers = list(observers or [])
        self._has_observers = False
        self._supports_all = False
        self._supported_event_types = set()
        self._observers_by_event_type = {}
        self._observers_for_unknown_event_type = ()
        self._capture_event_types = None
        self._capture_unknown_event_types = False
        self.debug_mode = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = self._normalize_loader_result_policy(loader_result_policy)
        self.loader_result_sample_size = max(1, loader_result_sample_size)
        self.run_id = run_id or generate_run_id()
        self.mode = mode
        self.max_recorded_events = self._normalize_max_recorded_events(max_recorded_events)
        self.capture_overflow_policy = self._normalize_capture_overflow_policy(capture_overflow_policy)
        self._lock = threading.RLock()
        self._diagnostic_warning_emitted = False
        self._seq = 0
        self._recorded_events = deque()
        self._rebuild_subscription_cache()

    def __getstate__(self) -> dict[str, Any]:
        state = dict(self.__dict__)
        state.pop("_lock", None)
        state.pop("_observers_by_event_type", None)
        state.pop("_observers_for_unknown_event_type", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()
        state_map = self.__dict__
        _ = state_map.setdefault("_has_observers", bool(state_map.get("observers", [])))
        _ = state_map.setdefault("_supports_all", False)
        _ = state_map.setdefault("_supported_event_types", set())
        _ = state_map.setdefault("_observers_by_event_type", {})
        _ = state_map.setdefault("_observers_for_unknown_event_type", ())
        _ = state_map.setdefault("_capture_event_types", None)
        _ = state_map.setdefault("_capture_unknown_event_types", False)
        _ = state_map.setdefault("max_recorded_events", _DEFAULT_MAX_RECORDED_EVENTS)
        _ = state_map.setdefault("capture_overflow_policy", "raise")

        self.max_recorded_events = self._normalize_max_recorded_events(cast("int | None", state_map.get("max_recorded_events")))
        self.capture_overflow_policy = self._normalize_capture_overflow_policy(str(state_map.get("capture_overflow_policy") or "raise"))

        recorded = state_map.get("_recorded_events")
        if recorded is None:
            self._recorded_events = deque()
        elif not isinstance(recorded, deque):
            self._recorded_events = deque(recorded)
        self._rebuild_subscription_cache()

    def _normalize_max_recorded_events(self, max_recorded_events: int | None) -> int | None:
        if max_recorded_events is None:
            return None
        resolved = int(max_recorded_events)
        if resolved < 0:
            msg = "max_recorded_events must be >= 0 or None"
            raise ValueError(msg)
        return resolved

    def _normalize_capture_overflow_policy(self, policy: str) -> str:
        normalized = (policy or "raise").strip().lower().replace("_", "-")
        if normalized not in _CAPTURE_OVERFLOW_POLICIES:
            msg = f"Unknown capture_overflow_policy: '{policy}'"
            raise ValueError(msg)
        return normalized

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

    def summarize_result(self, result: Any) -> dict[str, Any]:
        return self._summarize_result(result)

    def sample_result(self, result: Any) -> Any:
        return self._sample_result(result)

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
                "Observer %s.%s raised exception",
                type(observer).__name__,
                method.__name__,
                exc_info=True,
            )

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _supports_safely(self, observer: Observer, event_type: str) -> bool:
        try:
            return observer.supports(event_type)
        except Exception:  # noqa: BLE001
            return False

    def _infer_eventdispatch_observer_event_types(self, observer: "EventDispatchObserver") -> "tuple[str, ...]":
        dispatch_map = getattr(observer, "dispatch_map", None)
        if not isinstance(dispatch_map, dict):
            return ()

        dispatch_map = cast("dict[str, str]", dispatch_map)
        supported: list[str] = []
        for event_type, handler_name in dispatch_map.items():
            if event_type not in _CATALOG_EVENT_TYPES_SET:
                continue
            handler = getattr(observer, handler_name, None)
            if handler is None or not callable(handler):
                continue
            supported.append(event_type)
        return tuple(supported)

    def _infer_observer_subscriptions(self, observer: Observer) -> "tuple[str, ...]":
        supports_attr = getattr(type(observer), "supports", None)
        event_types = getattr(observer, "event_types", None)
        on_event_attr = getattr(type(observer), "on_event", None)

        if (
            isinstance(observer, EventDispatchObserver)
            and on_event_attr is EventDispatchObserver.on_event
            and event_types is None
            and supports_attr is Observer.supports
        ):
            return self._infer_eventdispatch_observer_event_types(observer)

        if supports_attr is Observer.supports:
            if event_types is None:
                return _CATALOG_EVENT_TYPES
            return tuple(event_type for event_type in event_types if event_type in _CATALOG_EVENT_TYPES_SET)

        supported: list[str] = []
        for event_type in _CATALOG_EVENT_TYPES:
            if self._supports_safely(observer, event_type):
                supported.append(event_type)
        return tuple(supported)

    def _rebuild_subscription_cache(self) -> None:
        observers_by_event_type: dict[str, list[Observer]] = {event_type: [] for event_type in _CATALOG_EVENT_TYPES}
        # Observers that should receive unknown event types (explicit opt-in).
        unknown_observers: list[Observer] = []

        for observer in self.observers:
            observer_event_types = self._infer_observer_subscriptions(observer)
            for event_type in observer_event_types:
                observers_by_event_type[event_type].append(observer)
            if getattr(observer, "supports_unknown_event_types", False):
                unknown_observers.append(observer)

        supported_event_types: set[str] = {event_type for event_type, observers in observers_by_event_type.items() if observers}

        self._has_observers = bool(self.observers)
        self._supports_all = len(supported_event_types) == len(observers_by_event_type)
        self._supported_event_types = supported_event_types
        self._observers_by_event_type = {
            event_type: tuple(observers) for event_type, observers in observers_by_event_type.items() if observers
        }
        self._observers_for_unknown_event_type = tuple(unknown_observers)

    def _should_emit_event_type(self, event_type: str) -> bool:
        if self.mode == "capture":
            if self._capture_event_types is None:
                return True
            return event_type in self._capture_event_types
        if not self._has_observers:
            return False
        return event_type in self._supported_event_types

    def register(self, observer: Observer) -> None:
        with self._lock:
            self._has_observers = True
            self.observers.append(observer)
            self._rebuild_subscription_cache()

    def unregister(self, observer: Observer) -> bool:
        with self._lock:
            try:
                self.observers.remove(observer)
            except ValueError:
                return False
            self._rebuild_subscription_cache()
            return True

    def clear(self) -> None:
        with self._lock:
            self.observers.clear()
            self._recorded_events.clear()
            self._rebuild_subscription_cache()

    def _record_event(self, event: Event) -> None:
        max_recorded_events = self.max_recorded_events
        if max_recorded_events is None:
            self._recorded_events.append(event)
            return

        limit = int(max_recorded_events)
        if limit <= 0:
            if self.capture_overflow_policy == "raise":
                msg = (
                    "ObserverManager capture recorded events overflow (limit=0). "
                    "Set max_recorded_events to a positive value, or set capture_overflow_policy to 'drop-oldest'/'drop-newest'."
                )
                raise ObserverCaptureOverflowError(msg)
            return

        if len(self._recorded_events) < limit:
            self._recorded_events.append(event)
            return

        policy = self.capture_overflow_policy
        if policy == "drop-newest":
            return
        if policy == "drop-oldest":
            _ = self._recorded_events.popleft()
            self._recorded_events.append(event)
            return

        msg = (
            f"ObserverManager capture recorded events overflow (size={len(self._recorded_events)}, limit={limit}, policy={policy}). "
            "Increase max_recorded_events, or set capture_overflow_policy to 'drop-oldest'/'drop-newest'."
        )
        raise ObserverCaptureOverflowError(msg)

    def emit(self, event: Event) -> None:
        if self.mode == "capture":
            self._record_event(event)
            return
        if not self._has_observers:
            return
        event_type = event.event_type
        if event_type in _CATALOG_EVENT_TYPES_SET:
            observers = self._observers_by_event_type.get(event_type)
            if not observers:
                return
            for observer in observers:
                self._safe_call(observer, observer.on_event, event)
            return

        observers = self._observers_for_unknown_event_type
        if not observers:
            return
        for observer in observers:
            if not self._supports_safely(observer, event_type):
                continue
            self._safe_call(observer, observer.on_event, event)

    def wants(self, event_type: str) -> bool:
        if event_type in _CATALOG_EVENT_TYPES_SET:
            return self._should_emit_event_type(event_type)
        if self.mode == "capture":
            return self._capture_unknown_event_types
        if not self._has_observers:
            return False
        return bool(self._observers_for_unknown_event_type)

    def emit_event(self, event_type: str, payload: Any, meta: dict[str, Any] | None = None) -> Event:
        event = Event(
            event_type=event_type,
            timestamp=now_ts(),
            run_id=self.run_id,
            payload=payload,
            meta=meta or {},
            seq=self._next_seq(),
        )
        self.emit(event)
        return event

    def drain_events(self) -> list[Event]:
        if not self._recorded_events:
            return []
        events = list(self._recorded_events)
        self._recorded_events.clear()
        return events

    def close(self) -> None:
        with self._lock:
            for observer in self.observers:
                if not hasattr(observer, "close"):
                    continue
                try:
                    observer.close()
                except Exception:
                    if self.debug_mode:
                        raise
                    _logger.warning(
                        "Observer %s.close raised exception",
                        type(observer).__name__,
                        exc_info=True,
                    )

    def create_capture_manager(self) -> "ObserverManager":
        capture = ObserverManager(
            observers=None,
            enable_debugging=self.debug_mode,
            fallback_logger_enabled=self.fallback_logger_enabled,
            loader_result_policy=self.loader_result_policy,
            loader_result_sample_size=self.loader_result_sample_size,
            run_id=self.run_id,
            mode="capture",
            max_recorded_events=self.max_recorded_events,
            capture_overflow_policy=self.capture_overflow_policy,
        )
        capture._capture_event_types = set(self._supported_event_types)
        capture._capture_unknown_event_types = bool(self._observers_for_unknown_event_type)
        return capture

    # ---- typed emit helpers ----

    def emit_pipeline_start(self, targets: list[str], batch_size: int) -> None:
        if not self._should_emit_event_type(EVENT_PIPELINE_START):
            return
        payload = PipelineStartEvent(targets, batch_size)
        _ = self.emit_event(EVENT_PIPELINE_START, payload)

    def emit_pipeline_end(self, total_batches: int, total_duration: float) -> None:
        if not self._should_emit_event_type(EVENT_PIPELINE_END):
            return
        payload = PipelineEndEvent(total_batches, total_duration)
        _ = self.emit_event(EVENT_PIPELINE_END, payload)

    def emit_batch_start(self, batch_num: int, row_ids: list[Any]) -> None:
        if not self._should_emit_event_type(EVENT_BATCH_START):
            return
        payload = BatchStartEvent(batch_num, row_ids)
        _ = self.emit_event(EVENT_BATCH_START, payload)

    def emit_batch_end(self, batch_num: int, duration: float) -> None:
        if not self._should_emit_event_type(EVENT_BATCH_END):
            return
        payload = BatchEndEvent(batch_num, duration)
        _ = self.emit_event(EVENT_BATCH_END, payload)

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
    ) -> None:
        if not self._should_emit_event_type(EVENT_LOADER_CALL):
            return
        payload = result
        if self.loader_result_policy != "full":
            if self.loader_result_policy == "none":
                payload = None
            elif self.loader_result_policy == "summary":
                payload = self._summarize_result(result)
            elif self.loader_result_policy == "sample":
                payload = self._sample_result(result)
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
        _ = self.emit_event(EVENT_LOADER_CALL, event_payload)

    def emit_field_compute(
        self,
        field_key: str,
        row_id: Hashable,
        dependencies: dict[str, Any],
        result: Any,
    ) -> None:
        if not self._should_emit_event_type(EVENT_FIELD_COMPUTE):
            return
        payload = FieldComputeEvent(field_key, row_id, dependencies, result)
        _ = self.emit_event(EVENT_FIELD_COMPUTE, payload)

    def emit_error(self, error: Exception, context: dict[str, Any]) -> None:
        if not self._should_emit_event_type(EVENT_ERROR):
            return
        payload = ErrorEvent(error, context)
        _ = self.emit_event(EVENT_ERROR, payload)

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

        if self._should_emit_event_type(EVENT_DIAGNOSTIC_WARNING):
            payload = DiagnosticWarningEvent(
                message=message,
                source_id=source_id,
                field_id=field_id,
                lookup_key=lookup_key,
                row_id=row_id,
            )
            _ = self.emit_event(EVENT_DIAGNOSTIC_WARNING, payload)
        elif self.fallback_logger_enabled:
            _logger.warning(
                "[诊断] %s | source=%s field=%s row_id=%s lookup_key=%r",
                message,
                source_id,
                field_id,
                row_id,
                lookup_key,
            )

    def emit_field_slim(
        self,
        field_key: str,
        reason: str,
        batch_num: int,
        remaining_fields: int,
    ) -> None:
        if not self._should_emit_event_type(EVENT_FIELD_SLIM):
            return
        payload = FieldSlimEvent(field_key, reason, batch_num, remaining_fields)
        _ = self.emit_event(EVENT_FIELD_SLIM, payload)

    def emit_row_write(
        self,
        row_id: Hashable,
        field_count: int,
        batch_num: int,
        row_index: int,
    ) -> None:
        if not self._should_emit_event_type(EVENT_ROW_WRITE):
            return
        payload = RowWriteEvent(row_id, field_count, batch_num, row_index)
        _ = self.emit_event(EVENT_ROW_WRITE, payload)

    def emit_row_release(
        self,
        row_id: Hashable,
        released_fields: list[str],
        retained_fields: list[str],
        batch_num: int,
    ) -> None:
        if not self._should_emit_event_type(EVENT_ROW_RELEASE):
            return
        payload = RowReleaseEvent(row_id, released_fields, retained_fields, batch_num)
        _ = self.emit_event(EVENT_ROW_RELEASE, payload)

    def emit_loader_slim(
        self,
        loader_name: str,
        original_keys: int,
        extracted_fields: list[str],
        batch_num: int,
    ) -> None:
        if not self._should_emit_event_type(EVENT_LOADER_SLIM):
            return
        payload = LoaderSlimEvent(loader_name, original_keys, extracted_fields, batch_num)
        _ = self.emit_event(EVENT_LOADER_SLIM, payload)

    def emit_column_write(
        self,
        field_key: str,
        row_count: int,
        batch_num: int,
    ) -> None:
        if not self._should_emit_event_type(EVENT_COLUMN_WRITE):
            return
        payload = ColumnWriteEvent(field_key, row_count, batch_num)
        _ = self.emit_event(EVENT_COLUMN_WRITE, payload)

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
    ) -> None:
        if not self._should_emit_event_type(EVENT_RELATION_LOOKUP):
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
        _ = self.emit_event(EVENT_RELATION_LOOKUP, payload)

    def emit_stage_span(self, stage: str, batch_num: int, duration: float) -> None:
        if not self._should_emit_event_type(EVENT_STAGE_SPAN):
            return
        payload = StageSpanEvent(stage=stage, batch_num=batch_num, duration=duration)
        _ = self.emit_event(EVENT_STAGE_SPAN, payload)


__all__ = [
    "ObserverManager",
]
