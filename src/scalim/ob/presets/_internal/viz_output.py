import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Any, Dict, Optional, cast

from .viz_config import VizObserverConfig
from .viz_config import default_viz_dir as _default_viz_dir
from .viz_config import normalize_output_dir as _normalize_output_dir

_LOGGER = logging.getLogger(__name__)


class VizEventEmitter:
    _output_handle: Optional[IO[str]]
    _logger: logging.Logger

    def __init__(self, path: Optional[str], *, logger: Optional[logging.Logger] = None, append: bool = True) -> None:
        self._logger = logger or _LOGGER
        self._output_handle = None
        if not path:
            return
        try:
            resolved = Path(path)
            if resolved.parent and not resolved.parent.exists():
                resolved.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
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


class VizObserverOutputMixin(ABC):
    config: VizObserverConfig = cast("VizObserverConfig", object())
    snapshot: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None
    _events_emitter: Optional[VizEventEmitter] = None
    _trace_emitter: Optional[VizEventEmitter] = None
    _snapshot_written: bool = False
    _run_dir_applied: bool = False

    @abstractmethod
    def _normalize_node_ref(self, node_ref: Dict[str, str]) -> Dict[str, str]: ...

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
        snapshot = self.snapshot
        if not snapshot or not isinstance(snapshot, dict):
            return
        meta = snapshot.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            snapshot["meta"] = meta
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
        snapshot = self.snapshot
        if not snapshot_path or not snapshot:
            return
        try:
            path = Path(snapshot_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, ensure_ascii=False, indent=2, default=str)
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

    def close(self) -> None:
        if self._events_emitter is not None:
            self._events_emitter.close()
            self._events_emitter = None
        if self._trace_emitter is not None:
            self._trace_emitter.close()
            self._trace_emitter = None
