# region imports

import json
import logging
import os
import platform
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO, Any, Dict, Optional, Sequence, Set, Tuple, cast

from ..._project_constants import VIZ_DIR_NAME
from ...events.events import (
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
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
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
    return str(base / VIZ_DIR_NAME)


def _normalize_output_dir(base_dir: str) -> str:
    normalized = Path(base_dir).expanduser()
    base_name = normalized.name
    parent_name = normalized.parent.name
    if VIZ_DIR_NAME not in (base_name, parent_name):
        normalized = normalized / VIZ_DIR_NAME
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
        value = _normalize_dict_keys(cast("Dict[Any, Any]", value))
    if isinstance(value, dict):
        value_dict = cast("Dict[Any, Any]", value)
        return dict(list(value_dict.items())[:size])
    if isinstance(value, (list, tuple)):
        value_seq = cast("Sequence[Any]", value)
        return list(value_seq[:size])
    if isinstance(value, set):
        value_set = cast("Set[Any]", value)
        return list(list(value_set)[:size])
    return value


def _normalize_dict_keys(value: Dict[Any, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, item in value.items():
        item_value = item
        if isinstance(item_value, dict):
            item_value = _normalize_dict_keys(cast("Dict[Any, Any]", item_value))
        normalized[str(key)] = item_value
    return normalized


@dataclass
class VizObserverConfig:
    output_path: Optional[str] = None
    """事件输出文件路径(优先级高于 `output_dir`)."""

    output_dir: Optional[str] = None
    """输出目录;在未显式提供 `output_path`/`snapshot_path`/`trace_path` 时用于推导各输出文件路径."""

    snapshot_path: Optional[str] = None
    """快照输出文件路径(写入 `viz_snapshot.json`)."""

    trace_path: Optional[str] = None
    """追踪输出文件路径(写入 `viz_trace.jsonl`,需 `trace_enabled=True`)."""

    events_filename: str = "viz_events.jsonl"
    """当使用 `output_dir` 推导路径时的事件文件名."""

    trace_filename: str = "viz_trace.jsonl"
    """当使用 `output_dir` 推导路径时的追踪文件名."""

    snapshot_filename: str = "viz_snapshot.json"
    """当使用 `output_dir` 推导路径时的快照文件名."""

    use_default_output_dir: bool = False
    """是否在未提供 `output_dir` 时使用默认目录(不同系统下会落到不同的配置目录)."""

    trace_enabled: bool = False
    """是否启用追踪输出(除非显式启用,否则仅输出事件与快照)."""

    append: bool = False
    """是否以追加方式写入 `*.jsonl` 输出(避免覆盖既有结果)."""

    payload_policy: str = "summary"
    """事件负载策略:`summary`/`sample`/`full`/`none`."""

    sample_size: int = 5
    """当负载策略包含 `sample` 时,样本截断大小."""

    run_name: Optional[str] = None
    """可选的运行名称(写入 `snapshot.meta.viz.run_name`)."""

    env: Optional[str] = None
    """可选的环境标识(写入 `snapshot.meta.viz.env`)."""

    logger: logging.Logger = field(default=_LOGGER)
    """用于输出告警/异常日志的 `logging.Logger`."""

    def is_enabled(self) -> bool:
        events_path, snapshot_path, trace_path = self.resolve_output_paths()
        return bool(events_path or snapshot_path or (trace_path and self.trace_enabled_effective()))

    def trace_enabled_effective(self) -> bool:
        return bool(self.trace_enabled)

    def has_explicit_paths(self) -> bool:
        return bool(self.output_path or self.snapshot_path or self.trace_path)

    def _resolve_output_dir(self) -> Optional[str]:
        output_dir = self.output_dir
        if output_dir is None and self.use_default_output_dir:
            output_dir = _default_viz_dir()
        if output_dir:
            return _normalize_output_dir(output_dir)
        return None

    @staticmethod
    def _expand_user_path(path: Optional[str]) -> Optional[str]:
        if not path:
            return path
        return str(Path(path).expanduser())

    def _fill_paths_from_output_dir(
        self,
        output_dir: str,
        events_path: Optional[str],
        snapshot_path: Optional[str],
        trace_path: Optional[str],
    ) -> "Tuple[Optional[str], Optional[str], Optional[str]]":
        base = Path(output_dir)
        if events_path is None:
            events_path = str(base / self.events_filename)
        if snapshot_path is None:
            snapshot_path = str(base / self.snapshot_filename)
        if trace_path is None:
            trace_path = str(base / self.trace_filename)
        return events_path, snapshot_path, trace_path

    def _infer_trace_path(
        self,
        trace_path: Optional[str],
        events_path: Optional[str],
        snapshot_path: Optional[str],
    ) -> Optional[str]:
        if trace_path is not None:
            return trace_path
        base_dir = None
        if events_path:
            base_dir = Path(events_path).parent
        elif snapshot_path:
            base_dir = Path(snapshot_path).parent
        if base_dir is None:
            return None
        return str(base_dir / self.trace_filename)

    def resolve_output_paths(self) -> "Tuple[Optional[str], Optional[str], Optional[str]]":
        output_dir = self._resolve_output_dir()
        events_path = self._expand_user_path(self.output_path)
        snapshot_path = self._expand_user_path(self.snapshot_path)
        trace_path = self._expand_user_path(self.trace_path)
        if output_dir:
            return self._fill_paths_from_output_dir(output_dir, events_path, snapshot_path, trace_path)
        trace_path = self._infer_trace_path(trace_path, events_path, snapshot_path)
        return events_path, snapshot_path, trace_path

    @classmethod
    def default_local(cls, **kwargs: Any) -> "VizObserverConfig":
        return cls(output_dir=_default_viz_dir(), **kwargs)


class VizEventEmitter:
    _output_handle: Optional[IO[str]]
    _logger: logging.Logger

    def __init__(self, path: Any, *, logger: Optional[logging.Logger] = None, append: bool = True) -> None:
        resolved_logger = logger or _LOGGER
        resolved_path = str(path)
        resolved_append = append
        if isinstance(path, VizObserverConfig):
            config = path
            resolved_logger = config.logger
            events_path, _, _ = config.resolve_output_paths()
            resolved_path = events_path or ""
            resolved_append = True

        self._logger = resolved_logger
        self._output_handle = None
        if not resolved_path:
            return
        try:
            resolved = Path(resolved_path)
            if resolved.parent and not resolved.parent.exists():
                resolved.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if resolved_append else "w"
            self._output_handle = resolved.open(mode, encoding="utf-8")
        except OSError as exc:
            self._logger.warning("[VizObserver] 打开输出路径失败: %s", exc)
            self._output_handle = None

    def emit(self, event: Dict[str, Any]) -> None:
        if self._output_handle:
            try:
                line = json.dumps(event, ensure_ascii=False, default=str)
                _ = self._output_handle.write(line + "\n")
                self._output_handle.flush()
            except OSError as exc:
                self._logger.warning("[VizObserver] 写入事件失败: %s", exc)

    def close(self, timeout: float = 2.0) -> None:
        _ = timeout
        if self._output_handle:
            self._output_handle.close()
            self._output_handle = None


class VizObserver(EventDispatchObserver):
    """可视化事件观察者."""

    config: VizObserverConfig
    snapshot: Optional[Dict[str, Any]]
    run_id: Optional[str]
    _events_emitter: Optional[VizEventEmitter]
    _trace_emitter: Optional[VizEventEmitter]
    _known_node_ids: Optional[Set[str]]
    _node_id_cache: Dict[str, str]
    _snapshot_written: bool
    _run_dir_applied: bool

    def __init__(
        self,
        *,
        config: Optional[VizObserverConfig] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        if config is None:
            config = VizObserverConfig()
        self.config = config
        self.snapshot = snapshot
        self.run_id = None
        self._events_emitter = None
        self._trace_emitter = None
        self._known_node_ids = None
        self._node_id_cache = {}
        self._snapshot_written = False
        self._run_dir_applied = False
        self._attach_viz_metadata()

    @classmethod
    def from_plan(cls, plan: ExecutionPlan, config: VizObserverConfig) -> "VizObserver":
        snapshot = plan.to_viz_graph_snapshot()
        return cls(config=config, snapshot=snapshot)

    @override
    def supports(self, event_type: str) -> bool:
        if event_type in ("field_compute", "row_write", "row_release", "relation_lookup"):
            return self.config.trace_enabled_effective()
        return True

    def _ensure_run_id(self) -> None:
        if self.run_id is not None:
            return
        self.run_id = "run_{}".format(int(time.time() * 1000))

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
        if self.config.output_path or self.config.snapshot_path or self.config.trace_path:
            self._run_dir_applied = True
            return
        output_dir = _normalize_output_dir(base_dir)
        run_dir = str(Path(output_dir) / self.run_id)
        self.config.output_dir = run_dir
        self._run_dir_applied = True

    def _open_append(self) -> bool:
        if not self.config.has_explicit_paths():
            return True
        return bool(self.config.append)

    def _ensure_emitters(self) -> None:
        if self._events_emitter is not None or self._trace_emitter is not None:
            return
        self._apply_run_output_dir()
        self._write_snapshot_if_needed()
        events_path, _, trace_path = self.config.resolve_output_paths()
        append = self._open_append()
        if events_path:
            self._events_emitter = VizEventEmitter(events_path, logger=self.config.logger, append=append)
        if self.config.trace_enabled_effective() and trace_path:
            self._trace_emitter = VizEventEmitter(trace_path, logger=self.config.logger, append=append)

    def _attach_viz_metadata(self) -> None:
        if not self.snapshot or not isinstance(self.snapshot, dict):
            return
        meta = self.snapshot.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            self.snapshot["meta"] = meta
        meta = cast("Dict[str, Any]", meta)
        viz_meta = meta.get("viz")
        if not isinstance(viz_meta, dict):
            viz_meta = {}
        viz_meta = cast("Dict[str, Any]", viz_meta)
        trace_enabled = self.config.trace_enabled_effective()
        viz_meta.update(
            {
                "payload_policy": self.config.payload_policy,
                "sample_size": self.config.sample_size,
                "trace_enabled": trace_enabled,
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
        _, snapshot_path, _ = self.config.resolve_output_paths()
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
            self.config.logger.warning("[VizObserver] 写入快照失败: %s", exc)

    def _select_payload(self, summary: Dict[str, Any], sample: Dict[str, Any], full: Dict[str, Any]) -> Dict[str, Any]:
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

    def _emit_to(self, emitter: Optional[VizEventEmitter], event_type: str, node_ref: Dict[str, str], payload: Dict[str, Any]) -> None:
        if not self.config.is_enabled():
            return
        if emitter is None:
            return
        if self.run_id is None:
            return
        normalized_node_ref = self._normalize_node_ref(node_ref)
        event = {
            "schema_version": "vizevent/v1",
            "run_id": self.run_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "node_ref": normalized_node_ref,
            "payload": payload,
        }
        emitter.emit(event)

    def _emit_event(self, event_type: str, node_ref: Dict[str, str], payload: Dict[str, Any]) -> None:
        self._emit_to(self._events_emitter, event_type, node_ref, payload)

    def _emit_trace(self, event_type: str, node_ref: Dict[str, str], payload: Dict[str, Any]) -> None:
        if not self.config.trace_enabled_effective():
            return
        self._emit_to(self._trace_emitter, event_type, node_ref, payload)

    @staticmethod
    def _canonical_loader_name(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if " " in raw:
            return raw.split(" ", 1)[0].strip()
        return raw

    def _get_known_node_ids(self) -> Set[str]:
        if self._known_node_ids is not None:
            return self._known_node_ids
        known: Set[str] = set()
        if self.snapshot and isinstance(self.snapshot, dict):
            nodes = self.snapshot.get("nodes")
            if isinstance(nodes, list):
                for item_dict in cast("Sequence[Dict[str, Any]]", nodes):
                    node_id = item_dict.get("id")
                    if node_id:
                        known.add(str(node_id))
        self._known_node_ids = known
        return known

    def _normalize_node_ref_id(self, node_id: str) -> str:
        raw = str(node_id or "").strip()
        if not raw:
            return ""
        cached = self._node_id_cache.get(raw)
        if cached is not None:
            return cached

        known = self._get_known_node_ids()
        if not known or raw in known:
            self._node_id_cache[raw] = raw
            return raw

        if " " in raw:
            trimmed = raw.split(" ", 1)[0].strip()
            if trimmed in known:
                self._node_id_cache[raw] = trimmed
                return trimmed

        if raw.startswith("field:"):
            prefix = "{}_".format(raw)
            candidates = [item for item in known if item.startswith(prefix)]
            if candidates:
                value = None
                for item in candidates:
                    if item.endswith("_value"):
                        value = item
                        break
                chosen = value or sorted(candidates)[0]
                self._node_id_cache[raw] = chosen
                return chosen

        self._node_id_cache[raw] = raw
        return raw

    def _normalize_node_ref(self, node_ref: Dict[str, str]) -> Dict[str, str]:
        raw_id = node_ref.get("id", "")
        if not raw_id:
            return node_ref
        normalized = self._normalize_node_ref_id(raw_id)
        if normalized and normalized != raw_id:
            return {"type": node_ref.get("type", ""), "id": normalized}
        return node_ref

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

    @override
    def close(self) -> None:
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
        if isinstance(full_event.get("result"), dict):
            full_event["result"] = _normalize_dict_keys(cast("Dict[Any, Any]", full_event["result"]))
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
            "error_type": type(event.error).__name__,
            "message": str(event.error),
        }
        if "row_id" in context:
            summary["row_id"] = str(context.get("row_id"))
        if context:
            summary["context_keys"] = list(context.keys())
        sample: Dict[str, Any] = {}
        if context:
            sample["context_sample"] = _sample_value(context, self.config.sample_size)
        full = {
            "error_type": type(event.error).__name__,
            "message": str(event.error),
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


__all__ = [
    "VizEventEmitter",
    "VizObserver",
    "VizObserverConfig",
]
