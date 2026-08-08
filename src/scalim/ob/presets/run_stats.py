# region imports

import json
import os
import warnings
from typing import Any, Dict, List, Optional, Set

from ...events import Event, EventType
from ...vendor.dataclassesx import dataclass, field
from ..observer import EventDispatchObserver

# endregion

SCHEMA_RUN_STATS = "scalim_run_stats/v1"
_STAGES = ("stream", "loader", "compute", "write")
BATCH_PERSIST_WARN_THRESHOLD = 500

HIGH_IMPACT_OBS_WARNING = (
    "scalim observability: enabling high-impact collection ({kind}) increases observation tax; "
    "prefer bench profile for low-drift evidence. kind={kind}"
)


def warn_high_impact_observability(kind):
    # type: (str) -> None
    warnings.warn(HIGH_IMPACT_OBS_WARNING.format(kind=str(kind)), UserWarning, stacklevel=2)


def _rss_mb():
    # type: () -> Optional[float]
    try:
        from ...vendor.compact.importlibx import import_module

        psutil = import_module("psutil")
        return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        return None


def _r2(value):
    # type: (Optional[float]) -> Optional[float]
    return None if value is None else round(float(value), 2)


def require_psutil_for_memory(reason):
    # type: (str) -> None
    try:
        from ...vendor.compact.importlibx import import_module

        import_module("psutil")
    except Exception as exc:
        raise RuntimeError(
            "memory sampling requested ({}) but psutil is not available; install optional psutil or use duration-only bench".format(reason)
        ) from exc


@dataclass
class RunStatsMeta:
    profile: Optional[str] = None
    tag: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class WorkflowStatsAccumulator(EventDispatchObserver):
    """Accumulate per-pipeline snapshots so workflow shared reset cannot erase evidence.

    Subscribes only to lite EventTypes (no RELATION_LOOKUP / ROW_WRITE / FIELD_COMPUTE).
    """

    event_types = {
        EventType.PIPELINE_START,
        EventType.PIPELINE_END,
        EventType.BATCH_START,
        EventType.BATCH_END,
        EventType.STAGE_SPAN,
        EventType.LOADER_CALL,
        EventType.OUTPUT_TARGET_END,
    }  # type: Set[EventType]

    def __init__(self, sample_rss=False, persist_batches=True):
        # type: (bool, bool) -> None
        self.sample_rss = bool(sample_rss)
        self.persist_batches = bool(persist_batches)
        self.nodes = []  # type: List[Dict[str, Any]]
        self._batch_persist_warned = False
        self._reset_current()

    def _reset_current(self):
        # type: () -> None
        self._pipeline_start_rss = _rss_mb() if self.sample_rss else None
        self._batches = []  # type: List[Dict[str, Any]]
        self._batch_index = {}  # type: Dict[int, Dict[str, Any]]
        self._loaders = {}  # type: Dict[str, Dict[str, Any]]
        self._outputs = []  # type: List[Dict[str, Any]]
        self._total_rows_in = 0
        self._batch_size = None  # type: Optional[int]

    def on_pipeline_start(self, event):
        # type: (Event) -> None
        self._reset_current()
        payload = event.payload
        self._batch_size = getattr(payload, "batch_size", None)

    def on_batch_start(self, event):
        # type: (Event) -> None
        payload = event.payload
        try:
            n_rows = len(payload.row_ids or [])
        except TypeError:
            n_rows = 0
        self._total_rows_in += n_rows
        entry = {
            "n": int(payload.batch_num),
            "duration_s": 0.0,
            "rows_in": n_rows,
            "stages": {k: 0.0 for k in _STAGES},
            "rss_mb": _rss_mb() if self.sample_rss else None,
            "loaders": [],
        }
        self._batch_index[int(payload.batch_num)] = entry
        if self.persist_batches:
            self._batches.append(entry)
            if (not self._batch_persist_warned) and len(self._batches) >= BATCH_PERSIST_WARN_THRESHOLD:
                self._batch_persist_warned = True
                warn_high_impact_observability("persist_batches_large")

    def on_batch_end(self, event):
        # type: (Event) -> None
        payload = event.payload
        entry = self._batch_index.get(int(payload.batch_num))
        if entry is None:
            return
        entry["duration_s"] = float(payload.duration)
        if self.sample_rss:
            entry["rss_mb"] = _rss_mb()

    def on_stage_span(self, event):
        # type: (Event) -> None
        payload = event.payload
        entry = self._batch_index.get(int(payload.batch_num))
        if entry is None:
            return
        stage = str(payload.stage)
        if stage in entry["stages"]:
            entry["stages"][stage] += max(0.0, float(payload.duration))

    def on_loader_call(self, event):
        # type: (Event) -> None
        payload = event.payload
        name = str(payload.loader_name)
        try:
            rows = len(payload.result) if payload.result is not None else 0
        except TypeError:
            rows = 0
        duration = float(payload.duration)
        agg = self._loaders.get(name)
        if agg is None:
            agg = {
                "name": name,
                "calls": 0,
                "total_s": 0.0,
                "records": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            }
            self._loaders[name] = agg
        agg["calls"] += 1
        agg["total_s"] += duration
        agg["records"] += rows
        if payload.cache_status == "hit":
            agg["cache_hits"] += 1
        elif payload.cache_status == "miss":
            agg["cache_misses"] += 1
        if payload.batch_num is not None:
            entry = self._batch_index.get(int(payload.batch_num))
            if entry is not None:
                entry["loaders"].append(
                    {
                        "name": name,
                        "duration_s": duration,
                        "rows": rows,
                        "cache": payload.cache_status,
                    }
                )

    def on_output_target_end(self, event):
        # type: (Event) -> None
        payload = event.payload
        self._outputs.append(
            {
                "target_id": payload.target_id,
                "rows": int(payload.row_count),
                "duration_s": float(payload.duration),
                "path": payload.output_path or "",
                "sheet_name": payload.sheet_name,
                "error_count": int(payload.error_count),
                "disabled": bool(payload.disabled),
            }
        )

    def on_pipeline_end(self, event):
        # type: (Event) -> None
        payload = event.payload
        end_rss = _rss_mb() if self.sample_rss else None
        stages_total = {k: 0.0 for k in _STAGES}
        for batch in self._batches:
            for key in _STAGES:
                stages_total[key] += float(batch["stages"].get(key, 0.0))
        if not self._batches:
            for entry in self._batch_index.values():
                for key in _STAGES:
                    stages_total[key] += float(entry["stages"].get(key, 0.0))
        loaders = []
        for name in sorted(self._loaders):
            item = dict(self._loaders[name])
            denom = item["cache_hits"] + item["cache_misses"]
            item["cache_hit_rate"] = (item["cache_hits"] / float(denom)) if denom else 0.0
            item["total_s"] = round(float(item["total_s"]), 4)
            loaders.append(item)
        peak_vals = [float(b["rss_mb"]) for b in self._batches if b.get("rss_mb") is not None]
        if end_rss is not None:
            peak_vals.append(float(end_rss))
        if self._pipeline_start_rss is not None:
            peak_vals.append(float(self._pipeline_start_rss))
        node = {
            "pipeline": {
                "batch_size": self._batch_size,
                "total_batches": int(getattr(payload, "total_batches", len(self._batch_index)) or len(self._batch_index)),
                "total_duration_s": round(float(getattr(payload, "total_duration", 0.0) or 0.0), 4),
                "total_rows_in": int(self._total_rows_in),
            },
            "memory": {
                "start_mb": _r2(self._pipeline_start_rss),
                "end_mb": _r2(end_rss),
                "peak_mb": _r2(max(peak_vals) if peak_vals else None),
                "increase_mb": _r2(None if end_rss is None or self._pipeline_start_rss is None else (end_rss - self._pipeline_start_rss)),
            },
            "stages_total": {k: round(v, 4) for k, v in stages_total.items()},
            "batches": list(self._batches) if self.persist_batches else [],
            "loaders": loaders,
            "outputs": list(self._outputs),
        }
        self.nodes.append(node)

    def build_run_stats(self, meta=None):
        # type: (Optional[Dict[str, Any]]) -> Dict[str, Any]
        stages_total = {k: 0.0 for k in _STAGES}
        loaders_map = {}  # type: Dict[str, Dict[str, Any]]
        outputs = []  # type: List[Dict[str, Any]]
        batches = []  # type: List[Dict[str, Any]]
        total_rows = 0
        total_duration = 0.0
        total_batches = 0
        peak_mb = None  # type: Optional[float]
        start_mb = None  # type: Optional[float]
        end_mb = None  # type: Optional[float]

        for node in self.nodes:
            pipe = node.get("pipeline") or {}
            total_rows += int(pipe.get("total_rows_in") or 0)
            total_duration += float(pipe.get("total_duration_s") or 0.0)
            total_batches += int(pipe.get("total_batches") or 0)
            for k in _STAGES:
                stages_total[k] += float((node.get("stages_total") or {}).get(k) or 0.0)
            for loader in node.get("loaders") or []:
                name = loader.get("name") or ""
                agg = loaders_map.get(name)
                if agg is None:
                    agg = {
                        "name": name,
                        "calls": 0,
                        "total_s": 0.0,
                        "records": 0,
                        "cache_hits": 0,
                        "cache_misses": 0,
                    }
                    loaders_map[name] = agg
                agg["calls"] += int(loader.get("calls") or 0)
                agg["total_s"] += float(loader.get("total_s") or 0.0)
                agg["records"] += int(loader.get("records") or 0)
                agg["cache_hits"] += int(loader.get("cache_hits") or 0)
                agg["cache_misses"] += int(loader.get("cache_misses") or 0)
            outputs.extend(list(node.get("outputs") or []))
            batches.extend(list(node.get("batches") or []))
            mem = node.get("memory") or {}
            if mem.get("peak_mb") is not None:
                peak_mb = float(mem["peak_mb"]) if peak_mb is None else max(peak_mb, float(mem["peak_mb"]))
            if start_mb is None and mem.get("start_mb") is not None:
                start_mb = float(mem["start_mb"])
            if mem.get("end_mb") is not None:
                end_mb = float(mem["end_mb"])

        loaders = []
        for name in sorted(loaders_map):
            item = dict(loaders_map[name])
            denom = item["cache_hits"] + item["cache_misses"]
            item["cache_hit_rate"] = (item["cache_hits"] / float(denom)) if denom else 0.0
            item["total_s"] = round(float(item["total_s"]), 4)
            loaders.append(item)
        loaders.sort(key=lambda x: -float(x.get("total_s") or 0.0))

        return {
            "schema": SCHEMA_RUN_STATS,
            "meta": dict(meta or {}),
            "pipeline": {
                "total_duration_s": round(total_duration, 4),
                "total_batches": int(total_batches),
                "total_rows_in": int(total_rows),
                "throughput_rows_s": round(total_rows / total_duration, 2) if total_duration > 0 else None,
                "node_count": len(self.nodes),
            },
            "memory": {
                "start_mb": _r2(start_mb),
                "end_mb": _r2(end_mb),
                "peak_mb": _r2(peak_mb),
                "increase_mb": _r2(None if start_mb is None or end_mb is None else (end_mb - start_mb)),
            },
            "stages_total": {k: round(float(v), 4) for k, v in stages_total.items()},
            "batches": batches,
            "loaders": loaders,
            "outputs": outputs,
            "nodes": list(self.nodes),
            "notes": {
                "write_stage_attribution": "sink_path_timed",
                "shared_observer_reset": "use_nodes_not_last_pipeline_only",
                "sink_close_bucket": "write",
            },
        }


def atomic_write_run_stats_json(path, payload):
    # type: (str, Dict[str, Any]) -> str
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    tmp = "{}.tmp.{}".format(path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def write_run_stats_sibling(run_dir, payload, filename="run_stats.json"):
    # type: (str, Dict[str, Any], str) -> str
    """Write run_stats next to a viz/run artifact directory (sibling file, not embedded)."""
    path = os.path.join(str(run_dir), str(filename))
    return atomic_write_run_stats_json(path, payload)


__all__ = (
    "SCHEMA_RUN_STATS",
    "HIGH_IMPACT_OBS_WARNING",
    "RunStatsMeta",
    "WorkflowStatsAccumulator",
    "atomic_write_run_stats_json",
    "require_psutil_for_memory",
    "warn_high_impact_observability",
    "write_run_stats_sibling",
)
