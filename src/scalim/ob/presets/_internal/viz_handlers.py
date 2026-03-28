from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Sequence, Set, cast

from ....events._events import (
    AdaptiveSchedulerDecisionEvent,
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    OutputTargetEndEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)
from ....vendor.dataclassesx import asdict
from .viz_config import VizObserverConfig
from .viz_output import VizEventEmitter


def _safe_len(value: Any) -> int:
    try:
        return len(value)
    except (TypeError, AttributeError):
        return 0


def _normalize_dict_keys(value: Dict[Any, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, item in value.items():
        item_value = item
        if isinstance(item_value, dict):
            item_value = _normalize_dict_keys(cast("Dict[Any, Any]", item_value))  # pragma: allow-cast dict typed narrowing
        normalized[str(key)] = item_value
    return normalized


def _sample_value(value: Any, size: int) -> Any:
    if size <= 0:
        return None
    if value is None:
        return None
    if isinstance(value, dict):
        value = _normalize_dict_keys(cast("Dict[Any, Any]", value))  # pragma: allow-cast dict typed narrowing
    if isinstance(value, dict):
        value_dict = cast("Dict[Any, Any]", value)  # pragma: allow-cast dict typed narrowing
        return dict(list(value_dict.items())[:size])
    if isinstance(value, (list, tuple)):
        value_seq = cast("Sequence[Any]", value)  # pragma: allow-cast sequence typed narrowing
        return list(value_seq[:size])
    if isinstance(value, set):
        value_set = cast("Set[Any]", value)  # pragma: allow-cast set typed narrowing
        return list(list(value_set)[:size])
    return value


class VizObserverHandlerMixin(ABC):
    config: VizObserverConfig
    run_id: Optional[str] = None
    _events_emitter: Optional[VizEventEmitter] = None
    _trace_emitter: Optional[VizEventEmitter] = None

    @abstractmethod
    def _ensure_run_id(self) -> None: ...

    @abstractmethod
    def _ensure_emitters(self) -> None: ...

    @abstractmethod
    def _select_payload(self, summary: Dict[str, Any], sample: Dict[str, Any], full: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def _emit_event(self, event_type: str, node_ref: Dict[str, str], payload: Dict[str, Any]) -> None: ...

    @abstractmethod
    def _emit_trace(self, event_type: str, node_ref: Dict[str, str], payload: Dict[str, Any]) -> None: ...

    @staticmethod
    @abstractmethod
    def _canonical_loader_name(value: Any) -> str: ...

    def supports(self, event_type: str) -> bool:
        if event_type in ("field_compute", "row_write", "row_release", "relation_lookup"):
            return self.config.trace_enabled_effective()
        return True

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        if not self.config.is_enabled():
            return
        self._ensure_run_id()
        self._ensure_emitters()
        summary = {
            "targets": event.targets,
            "batch_size": event.batch_size,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("run_started", {"type": "pipeline", "id": "pipeline"}, payload)

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None and self._trace_emitter is None:
            return
        summary = {
            "total_batches": event.total_batches,
            "total_duration_ms": int(event.total_duration * 1000),
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("run_finished", {"type": "pipeline", "id": "pipeline"}, payload)
        if self._events_emitter is not None:
            self._events_emitter.close()
            self._events_emitter = None
        if self._trace_emitter is not None:
            self._trace_emitter.close()
            self._trace_emitter = None

    def on_batch_start(self, event: BatchStartEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "batch_num": event.batch_num,
            "row_count": len(event.row_ids),
        }
        sample = {
            "row_ids_sample": _sample_value([str(rid) for rid in event.row_ids], self.config.sample_size),
        }
        payload = self._select_payload(summary, sample, {"data": asdict(event)})
        self._emit_event("batch_started", {"type": "batch", "id": "batch:{}".format(event.batch_num)}, payload)

    def on_batch_end(self, event: BatchEndEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "batch_num": event.batch_num,
            "duration_ms": int(event.duration * 1000),
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("batch_finished", {"type": "batch", "id": "batch:{}".format(event.batch_num)}, payload)

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        display_loader_name = str(event.loader_name or "")
        canonical_loader_name = self._canonical_loader_name(display_loader_name)
        summary = {
            "loader_name": canonical_loader_name,
            "duration_ms": int(event.duration * 1000),
            "result_count": _safe_len(event.result),
            "cache_status": event.cache_status,
            "cache_scope": event.cache_scope,
            "lookup_key_count": event.lookup_key_count,
            "field_keys": event.field_keys,
        }
        if display_loader_name and canonical_loader_name and display_loader_name != canonical_loader_name:
            summary["loader_display_name"] = display_loader_name
        full_event = asdict(event)
        result_value = full_event.get("result")
        if isinstance(result_value, dict):
            full_event["result"] = _normalize_dict_keys(cast("Dict[Any, Any]", result_value))  # pragma: allow-cast dict typed narrowing
        sample = {
            "sample_size": self.config.sample_size,
            "sample": _sample_value(event.result, self.config.sample_size),
        }
        payload = self._select_payload(summary, sample, {"data": full_event})
        self._emit_event("loader_called", {"type": "loader", "id": "loader:{}".format(canonical_loader_name)}, payload)

    def on_field_compute(self, event: FieldComputeEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary = {
            "field_key": event.field_key,
            "row_id": str(event.row_id),
            "result_type": type(event.result).__name__,
            "is_null": event.result is None,
        }
        sample = {
            "result": event.result,
            "dependencies_sample": _sample_value(event.dependencies, self.config.sample_size),
        }
        payload = self._select_payload(summary, sample, {"data": asdict(event)})
        self._emit_trace("field_computed", {"type": "field", "id": "field:{}".format(event.field_key)}, payload)

    def on_error(self, event: ErrorEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        context = event.context if isinstance(event.context, dict) else {}
        field_key = context.get("field_key") or context.get("field_id") or context.get("field")
        loader_name = context.get("loader_name") or context.get("loader")
        source_id = context.get("source_id") or context.get("source")
        if field_key:
            node_ref = {"type": "field", "id": "field:{}".format(field_key)}
        elif loader_name:
            canonical = self._canonical_loader_name(loader_name)
            node_ref = {"type": "loader", "id": "loader:{}".format(canonical or loader_name)}
        elif source_id:
            node_ref = {"type": "source", "id": "source:{}".format(source_id)}
        else:
            node_ref = {"type": "pipeline", "id": "pipeline"}
        summary: Dict[str, Any] = {
            "error_type": event.error_type,
            "message": event.error_message,
        }
        if "row_id" in context:
            summary["row_id"] = str(context.get("row_id"))
        if context:
            summary["context_keys"] = list(context.keys())
        sample: Dict[str, Any] = {}
        if context:
            sample["context_sample"] = _sample_value(context, self.config.sample_size)
        full = {
            "error_type": event.error_type,
            "message": event.error_message,
            "context": context,
        }
        payload = self._select_payload(summary, sample, full)
        self._emit_event("error", node_ref, payload)

    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        node_ref = {"type": "field", "id": "field:{}".format(event.field_id)}
        summary = {
            "message": event.message,
            "source_id": event.source_id,
            "field_id": event.field_id,
            "row_id": str(event.row_id),
            "lookup_key": event.lookup_key,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("diagnostic_warning", node_ref, payload)

    def on_column_write(self, event: ColumnWriteEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "field_key": event.field_key,
            "row_count": event.row_count,
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("column_written", {"type": "field", "id": "field:{}".format(event.field_key)}, payload)

    def on_row_write(self, event: RowWriteEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary = {
            "row_id": str(event.row_id),
            "field_count": event.field_count,
            "row_index": event.row_index,
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_trace("row_written", {"type": "batch", "id": "batch:{}".format(event.batch_num)}, payload)

    def on_row_release(self, event: RowReleaseEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary = {
            "row_id": str(event.row_id),
            "released_fields_count": len(event.released_fields),
            "retained_fields_count": len(event.retained_fields),
            "batch_num": event.batch_num,
        }
        sample = {
            "released_fields_sample": _sample_value(event.released_fields, self.config.sample_size),
            "retained_fields_sample": _sample_value(event.retained_fields, self.config.sample_size),
        }
        payload = self._select_payload(summary, sample, {"data": asdict(event)})
        self._emit_trace("row_released", {"type": "batch", "id": "batch:{}".format(event.batch_num)}, payload)

    def on_field_slim(self, event: FieldSlimEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "field_key": event.field_key,
            "reason": event.reason,
            "remaining_fields": event.remaining_fields,
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("memory_released", {"type": "field", "id": "field:{}".format(event.field_key)}, payload)

    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        display_loader_name = str(event.loader_name or "")
        canonical_loader_name = self._canonical_loader_name(display_loader_name)
        summary = {
            "loader_name": canonical_loader_name,
            "original_keys": event.original_keys,
            "extracted_fields_count": len(event.extracted_fields),
            "batch_num": event.batch_num,
        }
        if display_loader_name and canonical_loader_name and display_loader_name != canonical_loader_name:
            summary["loader_display_name"] = display_loader_name
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("memory_released", {"type": "loader", "id": "loader:{}".format(canonical_loader_name)}, payload)

    def on_relation_lookup(self, event: RelationLookupEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary: Dict[str, Any] = {
            "field_key": event.field_key,
            "row_id": str(event.row_id),
            "target_source": event.target_source,
            "result": event.result,
        }
        if event.error_message:
            summary["error_message"] = event.error_message
        if event.fk_type:
            summary["fk_type"] = event.fk_type
        if event.expected_type:
            summary["expected_type"] = event.expected_type
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_trace("relation_lookup", {"type": "field", "id": "field:{}".format(event.field_key)}, payload)

    def on_stage_span(self, event: StageSpanEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "stage": event.stage,
            "batch_num": event.batch_num,
            "duration_ms": int(event.duration * 1000),
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event("stage_span", {"type": "batch", "id": "batch:{}".format(event.batch_num)}, payload)

    def on_adaptive_scheduler_decision(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary: Dict[str, Any] = {
            "batch_num": event.batch_num,
            "layer_index": event.layer_index,
            "decision": event.decision,
            "backend": event.backend,
        }
        if event.reason:
            summary["reason"] = event.reason
        if event.layer_task_count is not None:
            summary["layer_task_count"] = event.layer_task_count
        if event.process_failure_mode:
            summary["process_failure_mode"] = event.process_failure_mode
        if event.pool_limits:
            summary["pool_limits"] = event.pool_limits
        if event.pool_wait_ms_total:
            summary["pool_wait_ms_total"] = event.pool_wait_ms_total
        if event.pool_wait_ms_max:
            summary["pool_wait_ms_max"] = event.pool_wait_ms_max
        if event.pool_wait_count:
            summary["pool_wait_count"] = event.pool_wait_count
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event(
            "adaptive_scheduler_decision",
            {"type": "batch", "id": "batch:{}".format(event.batch_num)},
            payload,
        )

    def on_output_target_end(self, event: OutputTargetEndEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary: Dict[str, Any] = {
            "target_id": event.target_id,
            "row_count": int(event.row_count),
            "error_count": int(event.error_count),
            "duration_ms": int(event.duration * 1000),
            "disabled": bool(event.disabled),
        }
        if event.output_path:
            summary["output_path"] = str(event.output_path)
        if event.sheet_name:
            summary["sheet_name"] = str(event.sheet_name)
        if event.error_type:
            summary["error_type"] = str(event.error_type)
        if event.error_message:
            summary["error_message"] = str(event.error_message)
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit_event(
            "output_target_finished",
            {"type": "output_target", "id": "output_target:{}".format(event.target_id)},
            payload,
        )


__all__ = []
