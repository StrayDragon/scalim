from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Set, cast

from ....events import Event
from ....vendor.dataclassesx import asdict
from .viz_config import VizObserverConfig
from .viz_output import VizEventEmitter

if TYPE_CHECKING:
    from ....events._events import ErrorEvent


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

    def on_pipeline_start(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        self._ensure_run_id()
        self._ensure_emitters()
        summary = {
            "targets": payload.targets,
            "batch_size": payload.batch_size,
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("run_started", {"type": "pipeline", "id": "pipeline"}, payload_out)

    def on_pipeline_end(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None and self._trace_emitter is None:
            return
        summary = {
            "total_batches": payload.total_batches,
            "total_duration_ms": int(payload.total_duration * 1000),
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("run_finished", {"type": "pipeline", "id": "pipeline"}, payload_out)
        if self._events_emitter is not None:
            self._events_emitter.close()
            self._events_emitter = None
        if self._trace_emitter is not None:
            self._trace_emitter.close()
            self._trace_emitter = None

    def on_batch_start(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "batch_num": payload.batch_num,
            "row_count": len(payload.row_ids),
        }
        sample = {
            "row_ids_sample": _sample_value([str(rid) for rid in payload.row_ids], self.config.sample_size),
        }
        payload_out = self._select_payload(summary, sample, {"data": asdict(payload)})
        self._emit_event("batch_started", {"type": "batch", "id": "batch:{}".format(payload.batch_num)}, payload_out)

    def on_batch_end(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "batch_num": payload.batch_num,
            "duration_ms": int(payload.duration * 1000),
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("batch_finished", {"type": "batch", "id": "batch:{}".format(payload.batch_num)}, payload_out)

    def on_loader_call(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        display_loader_name = str(payload.loader_name or "")
        canonical_loader_name = self._canonical_loader_name(display_loader_name)
        summary = {
            "loader_name": canonical_loader_name,
            "duration_ms": int(payload.duration * 1000),
            "result_count": _safe_len(payload.result),
            "cache_status": payload.cache_status,
            "cache_scope": payload.cache_scope,
            "lookup_key_count": payload.lookup_key_count,
            "field_keys": payload.field_keys,
            "chunk_offset": payload.chunk_offset,
        }
        if display_loader_name and canonical_loader_name and display_loader_name != canonical_loader_name:
            summary["loader_display_name"] = display_loader_name
        full_event = asdict(payload)
        result_value = full_event.get("result")
        if isinstance(result_value, dict):
            full_event["result"] = _normalize_dict_keys(cast("Dict[Any, Any]", result_value))  # pragma: allow-cast dict typed narrowing
        sample = {
            "sample_size": self.config.sample_size,
            "sample": _sample_value(payload.result, self.config.sample_size),
        }
        payload_out = self._select_payload(summary, sample, {"data": full_event})
        self._emit_event("loader_called", {"type": "loader", "id": "loader:{}".format(canonical_loader_name)}, payload_out)

    def on_field_compute(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary = {
            "field_key": payload.field_key,
            "row_id": str(payload.row_id),
            "result_type": type(payload.result).__name__,
            "is_null": payload.result is None,
        }
        sample = {
            "result": payload.result,
            "dependencies_sample": _sample_value(payload.dependencies, self.config.sample_size),
        }
        payload_out = self._select_payload(summary, sample, {"data": asdict(payload)})
        self._emit_trace("field_computed", {"type": "field", "id": "field:{}".format(payload.field_key)}, payload_out)

    def on_error(self, event: Event) -> None:
        payload = cast("ErrorEvent", event.payload)  # pragma: allow-cast typed ErrorEvent payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        context = payload.context
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
            "error_type": payload.error_type,
            "message": payload.error_message,
        }
        if "row_id" in context:
            summary["row_id"] = str(context.get("row_id"))
        if context:
            summary["context_keys"] = list(context.keys())
        sample: Dict[str, Any] = {}
        if context:
            sample["context_sample"] = _sample_value(context, self.config.sample_size)
        full: Dict[str, Any] = {
            "error_type": payload.error_type,
            "message": payload.error_message,
            "context": context,
        }
        payload_out = self._select_payload(summary, sample, full)
        self._emit_event("error", node_ref, payload_out)

    def on_diagnostic_warning(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        node_ref = {"type": "field", "id": "field:{}".format(payload.field_id)}
        summary = {
            "message": payload.message,
            "source_id": payload.source_id,
            "field_id": payload.field_id,
            "row_id": str(payload.row_id),
            "lookup_key": payload.lookup_key,
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("diagnostic_warning", node_ref, payload_out)

    def on_column_write(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "field_key": payload.field_key,
            "row_count": payload.row_count,
            "batch_num": payload.batch_num,
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("column_written", {"type": "field", "id": "field:{}".format(payload.field_key)}, payload_out)

    def on_row_write(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary = {
            "row_id": str(payload.row_id),
            "field_count": payload.field_count,
            "row_index": payload.row_index,
            "batch_num": payload.batch_num,
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_trace("row_written", {"type": "batch", "id": "batch:{}".format(payload.batch_num)}, payload_out)

    def on_row_release(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary = {
            "row_id": str(payload.row_id),
            "released_fields_count": len(payload.released_fields),
            "retained_fields_count": len(payload.retained_fields),
            "batch_num": payload.batch_num,
        }
        sample = {
            "released_fields_sample": _sample_value(payload.released_fields, self.config.sample_size),
            "retained_fields_sample": _sample_value(payload.retained_fields, self.config.sample_size),
        }
        payload_out = self._select_payload(summary, sample, {"data": asdict(payload)})
        self._emit_trace("row_released", {"type": "batch", "id": "batch:{}".format(payload.batch_num)}, payload_out)

    def on_field_slim(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "field_key": payload.field_key,
            "reason": payload.reason,
            "remaining_fields": payload.remaining_fields,
            "batch_num": payload.batch_num,
        }
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("memory_released", {"type": "field", "id": "field:{}".format(payload.field_key)}, payload_out)

    def on_loader_slim(self, event: Event) -> None:
        payload = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        display_loader_name = str(payload.loader_name or "")
        canonical_loader_name = self._canonical_loader_name(display_loader_name)
        summary = {
            "loader_name": canonical_loader_name,
            "original_keys": payload.original_keys,
            "extracted_fields_count": len(payload.extracted_fields),
            "batch_num": payload.batch_num,
        }
        if display_loader_name and canonical_loader_name and display_loader_name != canonical_loader_name:
            summary["loader_display_name"] = display_loader_name
        payload_out = self._select_payload(summary, {}, {"data": asdict(payload)})
        self._emit_event("memory_released", {"type": "loader", "id": "loader:{}".format(canonical_loader_name)}, payload_out)

    def on_relation_lookup(self, event: Event) -> None:
        body = event.payload
        if not self.config.is_enabled():
            return
        if self._trace_emitter is None:
            return
        summary: Dict[str, Any] = {
            "field_key": body.field_key,
            "row_id": str(body.row_id),
            "target_source": body.target_source,
            "result": body.result,
        }
        if body.error_message:
            summary["error_message"] = body.error_message
        if body.fk_type:
            summary["fk_type"] = body.fk_type
        if body.expected_type:
            summary["expected_type"] = body.expected_type
        payload = self._select_payload(summary, {}, {"data": asdict(body)})
        self._emit_trace("relation_lookup", {"type": "field", "id": "field:{}".format(body.field_key)}, payload)

    def on_stage_span(self, event: Event) -> None:
        body = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary = {
            "stage": body.stage,
            "batch_num": body.batch_num,
            "duration_ms": int(body.duration * 1000),
        }
        payload = self._select_payload(summary, {}, {"data": asdict(body)})
        self._emit_event("stage_span", {"type": "batch", "id": "batch:{}".format(body.batch_num)}, payload)

    def on_adaptive_scheduler_decision(self, event: Event) -> None:
        body = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary: Dict[str, Any] = {
            "batch_num": body.batch_num,
            "layer_index": body.layer_index,
            "decision": body.decision,
            "backend": body.backend,
        }
        if body.reason:
            summary["reason"] = body.reason
        if body.layer_task_count is not None:
            summary["layer_task_count"] = body.layer_task_count
        if body.process_failure_mode:
            summary["process_failure_mode"] = body.process_failure_mode
        if body.pool_limits:
            summary["pool_limits"] = body.pool_limits
        if body.pool_wait_ms_total:
            summary["pool_wait_ms_total"] = body.pool_wait_ms_total
        if body.pool_wait_ms_max:
            summary["pool_wait_ms_max"] = body.pool_wait_ms_max
        if body.pool_wait_count:
            summary["pool_wait_count"] = body.pool_wait_count
        payload = self._select_payload(summary, {}, {"data": asdict(body)})
        self._emit_event(
            "adaptive_scheduler_decision",
            {"type": "batch", "id": "batch:{}".format(body.batch_num)},
            payload,
        )

    def on_output_target_end(self, event: Event) -> None:
        body = event.payload
        if not self.config.is_enabled():
            return
        if self._events_emitter is None:
            return
        summary: Dict[str, Any] = {
            "target_id": body.target_id,
            "row_count": int(body.row_count),
            "error_count": int(body.error_count),
            "duration_ms": int(body.duration * 1000),
            "disabled": bool(body.disabled),
        }
        if body.output_path:
            summary["output_path"] = str(body.output_path)
        if body.sheet_name:
            summary["sheet_name"] = str(body.sheet_name)
        if body.error_type:
            summary["error_type"] = str(body.error_type)
        if body.error_message:
            summary["error_message"] = str(body.error_message)
        payload = self._select_payload(summary, {}, {"data": asdict(body)})
        self._emit_event(
            "output_target_finished",
            {"type": "output_target", "id": "output_target:{}".format(body.target_id)},
            payload,
        )


__all__ = ()
