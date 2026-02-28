# region imports

import json
import logging
import os
import platform
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

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
from ...planning.plan import ExecutionPlan
from ...vendor.compact.typing_extensionsx import override
from ..observer import EventDispatchObserver

# endregion

_LOGGER = logging.getLogger(__name__)


def _default_viz_dir() -> str:
    system = platform.system().lower()
    if system.startswith("win") or os.name == "nt":
        base = Path(os.environ.get("APPDATA") or "~\\AppData\\Roaming").expanduser()
    elif system == "darwin":
        base = Path("~/Library/Application Support").expanduser()
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser()
    return str(base / "scalim-viz")


def _normalize_output_dir(base_dir: str) -> str:
    normalized = Path(base_dir).expanduser()
    base_name = normalized.name
    parent_name = normalized.parent.name
    if base_name != "scalim-viz" and parent_name != "scalim-viz":
        normalized = normalized / "scalim-viz"
    return str(normalized)


def _safe_len(value: Any) -> int:
    try:
        return len(value)
    except (TypeError, AttributeError):
        return 0


def _sample_value(value: Any, size: int) -> Any:
    if size <= 0:
        return None
    if value is None:
        return None
    if isinstance(value, dict):
        value = _normalize_dict_keys(cast("dict[Any, Any]", value))
    if isinstance(value, dict):
        value_dict = cast("dict[Any, Any]", value)
        return dict(list(value_dict.items())[:size])
    if isinstance(value, (list, tuple)):
        value_seq = cast("Sequence[Any]", value)
        return list(value_seq[:size])
    if isinstance(value, set):
        value_set = cast("set[Any]", value)
        return list(list(value_set)[:size])
    return value


def _normalize_dict_keys(value: dict[Any, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        item_value = item
        if isinstance(item_value, dict):
            item_value = _normalize_dict_keys(cast("dict[Any, Any]", item_value))
        normalized[str(key)] = item_value
    return normalized


@dataclass
class VizObserverConfig:
    output_path: str | None = None
    output_dir: str | None = None
    snapshot_path: str | None = None
    events_filename: str = "viz_events.jsonl"
    snapshot_filename: str = "viz_snapshot.json"
    use_default_output_dir: bool = False
    event_mode: str = "lite"
    payload_policy: str = "summary"
    sample_size: int = 5
    run_name: str | None = None
    env: str | None = None
    logger: logging.Logger = field(default=_LOGGER)

    def is_enabled(self) -> bool:
        events_path, snapshot_path = self.resolve_output_paths()
        return bool(events_path or snapshot_path)

    def resolve_output_paths(self) -> "tuple[str | None, str | None]":
        output_dir = self.output_dir
        if output_dir is None and self.use_default_output_dir:
            output_dir = _default_viz_dir()
        if output_dir:
            output_dir = _normalize_output_dir(output_dir)
        events_path = self.output_path
        snapshot_path = self.snapshot_path
        if events_path:
            events_path = str(Path(events_path).expanduser())
        if snapshot_path:
            snapshot_path = str(Path(snapshot_path).expanduser())
        if output_dir:
            if events_path is None:
                events_path = str(Path(output_dir) / self.events_filename)
            if snapshot_path is None:
                snapshot_path = str(Path(output_dir) / self.snapshot_filename)
        return events_path, snapshot_path

    @classmethod
    def default_local(cls, **kwargs: Any) -> "VizObserverConfig":
        return cls(output_dir=_default_viz_dir(), **kwargs)


class VizEventEmitter:
    config: VizObserverConfig
    _output_handle: IO[str] | None

    def __init__(self, config: VizObserverConfig) -> None:
        self.config = config
        self._output_handle = None

        events_path, _ = config.resolve_output_paths()
        if events_path:
            try:
                path = Path(events_path)
                if path.parent and not path.parent.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                self._output_handle = path.open("a", encoding="utf-8")
            except OSError as exc:
                config.logger.warning("[VizObserver] Failed to open output_path: %s", exc)
                self._output_handle = None

    def emit(self, event: dict[str, Any]) -> None:
        if self._output_handle:
            try:
                line = json.dumps(event, ensure_ascii=False, default=str)
                _ = self._output_handle.write(line + "\n")
                self._output_handle.flush()
            except OSError as exc:
                self.config.logger.warning("[VizObserver] Failed to write event: %s", exc)

    def close(self, timeout: float = 2.0) -> None:
        _ = timeout
        if self._output_handle:
            self._output_handle.close()
            self._output_handle = None


class VizObserver(EventDispatchObserver):
    """可视化事件观察者。"""

    config: VizObserverConfig
    snapshot: dict[str, Any] | None
    run_id: str | None
    _emitter: VizEventEmitter | None
    _snapshot_written: bool
    _run_dir_applied: bool

    def __init__(
        self,
        *,
        config: VizObserverConfig | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> None:
        if config is None:
            config = VizObserverConfig()
        self.config = config
        self.snapshot = snapshot
        self.run_id = None
        self._emitter = None
        self._snapshot_written = False
        self._run_dir_applied = False
        self._attach_viz_metadata()

    @classmethod
    def from_plan(cls, plan: ExecutionPlan, config: VizObserverConfig) -> "VizObserver":
        snapshot = plan.to_viz_graph_snapshot()
        return cls(config=config, snapshot=snapshot)

    def _ensure_run_id(self) -> None:
        if self.run_id is not None:
            return
        self.run_id = f"run_{int(time.time() * 1000)}"

    def _apply_run_output_dir(self) -> None:
        if self._run_dir_applied:
            return
        if not self.run_id:
            return
        if not self.config.output_dir:
            if self.config.use_default_output_dir:
                base_dir = _default_viz_dir()
            else:
                return
        else:
            base_dir = self.config.output_dir
        if self.config.output_path or self.config.snapshot_path:
            self._run_dir_applied = True
            return
        output_dir = _normalize_output_dir(base_dir)
        run_dir = str(Path(output_dir) / self.run_id)
        self.config.output_dir = run_dir
        self._run_dir_applied = True

    def _ensure_emitter(self) -> None:
        if self._emitter is not None:
            return
        self._apply_run_output_dir()
        self._write_snapshot_if_needed()
        self._emitter = VizEventEmitter(self.config)

    def _attach_viz_metadata(self) -> None:
        if self.snapshot is None:
            return
        meta = self.snapshot.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            self.snapshot["meta"] = meta
        meta = cast("dict[str, Any]", meta)
        viz_meta = meta.get("viz")
        if not isinstance(viz_meta, dict):
            viz_meta = {}
        viz_meta = cast("dict[str, Any]", viz_meta)
        viz_meta.update(
            {
                "event_mode": self.config.event_mode,
                "payload_policy": self.config.payload_policy,
                "sample_size": self.config.sample_size,
            }
        )
        if self.config.run_name:
            viz_meta["run_name"] = self.config.run_name
        if self.config.env:
            viz_meta["env"] = self.config.env
        meta["viz"] = viz_meta

    def _write_snapshot_if_needed(self) -> None:
        if self._snapshot_written:
            return
        _, snapshot_path = self.config.resolve_output_paths()
        if not snapshot_path or not self.snapshot:
            return
        try:
            path = Path(snapshot_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(self.snapshot, handle, ensure_ascii=False, indent=2, default=str)
            self._snapshot_written = True
        except OSError as exc:
            self.config.logger.warning("[VizObserver] Failed to write snapshot: %s", exc)

    def _select_payload(self, summary: dict[str, Any], sample: dict[str, Any], full: dict[str, Any]) -> dict[str, Any]:
        policy = (self.config.payload_policy or "summary").lower()
        if policy == "none":
            return {}
        if policy == "sample":
            payload = dict(summary)
            payload.update(sample)
            return payload
        if policy == "full":
            payload = dict(summary)
            payload.update(full)
            return payload
        return summary

    def _emit(self, event_type: str, node_ref: dict[str, str], payload: dict[str, Any]) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        if self.run_id is None:
            return
        if not self._should_emit(event_type):
            return
        event = {
            "schema_version": "vizevent/v1",
            "run_id": self.run_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "node_ref": node_ref,
            "payload": payload,
        }
        self._emitter.emit(event)

    def _should_emit(self, event_type: str) -> bool:
        mode = (self.config.event_mode or "lite").lower()
        return mode == "full" or event_type not in ("row_written", "row_released", "field_computed")

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        if not self.config.is_enabled():
            return
        self._ensure_run_id()
        self._ensure_emitter()
        summary = {
            "targets": event.targets,
            "batch_size": event.batch_size,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("run_started", {"type": "pipeline", "id": "pipeline"}, payload)

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "total_batches": event.total_batches,
            "total_duration_ms": int(event.total_duration * 1000),
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("run_finished", {"type": "pipeline", "id": "pipeline"}, payload)
        self._emitter.close()

    @override
    def close(self) -> None:
        if self._emitter is None:
            return
        self._emitter.close()
        self._emitter = None

    def on_batch_start(self, event: BatchStartEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "batch_num": event.batch_num,
            "row_count": len(event.row_ids),
        }
        sample = {
            "row_ids_sample": _sample_value([str(rid) for rid in event.row_ids], self.config.sample_size),
        }
        payload = self._select_payload(summary, sample, {"data": asdict(event)})
        self._emit("batch_started", {"type": "batch", "id": f"batch:{event.batch_num}"}, payload)

    def on_batch_end(self, event: BatchEndEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "batch_num": event.batch_num,
            "duration_ms": int(event.duration * 1000),
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("batch_finished", {"type": "batch", "id": f"batch:{event.batch_num}"}, payload)

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "loader_name": event.loader_name,
            "duration_ms": int(event.duration * 1000),
            "result_count": _safe_len(event.result),
            "cache_status": event.cache_status,
            "lookup_key_count": event.lookup_key_count,
            "field_keys": event.field_keys,
        }
        full_event = asdict(event)
        if isinstance(full_event.get("result"), dict):
            full_event["result"] = _normalize_dict_keys(cast("dict[Any, Any]", full_event["result"]))
        sample = {
            "sample_size": self.config.sample_size,
            "sample": _sample_value(event.result, self.config.sample_size),
        }
        payload = self._select_payload(summary, sample, {"data": full_event})
        self._emit("loader_called", {"type": "loader", "id": f"loader:{event.loader_name}"}, payload)

    def on_field_compute(self, event: FieldComputeEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
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
        self._emit("field_computed", {"type": "field", "id": f"field:{event.field_key}"}, payload)

    def on_error(self, event: ErrorEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        context = event.context
        field_key = context.get("field_key") or context.get("field_id") or context.get("field")
        loader_name = context.get("loader_name") or context.get("loader")
        source_id = context.get("source_id") or context.get("source")
        if field_key:
            node_ref = {"type": "field", "id": f"field:{field_key}"}
        elif loader_name:
            node_ref = {"type": "loader", "id": f"loader:{loader_name}"}
        elif source_id:
            node_ref = {"type": "source", "id": f"source:{source_id}"}
        else:
            node_ref = {"type": "pipeline", "id": "pipeline"}
        summary: dict[str, Any] = {
            "error_type": type(event.error).__name__,
            "message": str(event.error),
        }
        if "row_id" in context:
            summary["row_id"] = str(context.get("row_id"))
        if context:
            summary["context_keys"] = list(context.keys())
        sample: dict[str, Any] = {}
        if context:
            sample["context_sample"] = _sample_value(context, self.config.sample_size)
        full = {
            "error_type": type(event.error).__name__,
            "message": str(event.error),
            "context": context,
        }
        payload = self._select_payload(summary, sample, full)
        self._emit("error", node_ref, payload)

    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        node_ref = {"type": "field", "id": f"field:{event.field_id}"}
        summary = {
            "message": event.message,
            "source_id": event.source_id,
            "field_id": event.field_id,
            "row_id": str(event.row_id),
            "lookup_key": event.lookup_key,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("diagnostic_warning", node_ref, payload)

    def on_column_write(self, event: ColumnWriteEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "field_key": event.field_key,
            "row_count": event.row_count,
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("column_written", {"type": "field", "id": f"field:{event.field_key}"}, payload)

    def on_row_write(self, event: RowWriteEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "row_id": str(event.row_id),
            "field_count": event.field_count,
            "row_index": event.row_index,
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("row_written", {"type": "batch", "id": f"batch:{event.batch_num}"}, payload)

    def on_row_release(self, event: RowReleaseEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
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
        self._emit("row_released", {"type": "batch", "id": f"batch:{event.batch_num}"}, payload)

    def on_field_slim(self, event: FieldSlimEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "field_key": event.field_key,
            "reason": event.reason,
            "remaining_fields": event.remaining_fields,
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("memory_released", {"type": "field", "id": f"field:{event.field_key}"}, payload)

    def on_loader_slim(self, event: LoaderSlimEvent) -> None:
        if not self.config.is_enabled():
            return
        if self._emitter is None:
            return
        summary = {
            "loader_name": event.loader_name,
            "original_keys": event.original_keys,
            "extracted_fields_count": len(event.extracted_fields),
            "batch_num": event.batch_num,
        }
        payload = self._select_payload(summary, {}, {"data": asdict(event)})
        self._emit("memory_released", {"type": "loader", "id": f"loader:{event.loader_name}"}, payload)


__all__ = [
    "VizEventEmitter",
    "VizObserver",
    "VizObserverConfig",
]
