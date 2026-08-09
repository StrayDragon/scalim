# region imports

import json
import os
import warnings
from typing import Any, Dict, List, Optional, Set

from ...events import EventType
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

    event_types: Optional[Set[EventType]]
    sample_rss: bool
    persist_batches: bool
    nodes: List[Dict[str, Any]]
    _batch_persist_warned: bool
    _pipeline_start_rss: Optional[float]
    _batches: List[Dict[str, Any]]
    _batch_index: Dict[int, Dict[str, Any]]
    _loaders: Dict[str, Dict[str, Any]]
    _outputs: List[Dict[str, Any]]
    _total_rows_in: int
    _batch_size: Optional[int]
    _current_run_id: Optional[str]
    _current_demand_id: Optional[str]

    def __init__(self, sample_rss=False, persist_batches=True):
        # type: (bool, bool) -> None
        self.sample_rss = bool(sample_rss)
        self.persist_batches = bool(persist_batches)
        self.event_types = {
            EventType.PIPELINE_START,
            EventType.PIPELINE_END,
            EventType.BATCH_START,
            EventType.BATCH_END,
            EventType.STAGE_SPAN,
            EventType.LOADER_CALL,
            EventType.OUTPUT_TARGET_END,
        }
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
        self._current_run_id = None  # type: Optional[str]
        self._current_demand_id = None  # type: Optional[str]

    def on_pipeline_start(self, event):
        # type: (Event) -> None
        self._reset_current()
        payload = event.payload
        self._batch_size = getattr(payload, "batch_size", None)
        run_id = str(event.run_id or "").strip() or None
        meta = event.meta  # type: Dict[str, Any]
        demand_id = None  # type: Optional[str]
        for key in ("demand_id", "workflow_node_id", "node_id"):
            raw = meta.get(key)
            if raw is not None and str(raw).strip():
                demand_id = str(raw).strip()
                break
        self._current_run_id = run_id
        self._current_demand_id = demand_id or run_id

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
            "stages": dict.fromkeys(_STAGES, 0.0),
            "rss_mb": _rss_mb() if self.sample_rss else None,
            "loaders": [],
        }  # type: Dict[str, Any]
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
        stages = entry["stages"]  # type: Dict[str, float]
        if stage in stages:
            stages[stage] += max(0.0, float(payload.duration))

    def on_loader_call(self, event):
        # type: (Event) -> None
        payload = event.payload
        name = str(payload.loader_name)
        try:
            rows = len(payload.result) if payload.result is not None else 0
        except TypeError:
            rows = 0
        duration = float(payload.duration)
        existing = self._loaders.get(name)
        if existing is None:
            agg = {
                "name": name,
                "calls": 0,
                "total_s": 0.0,
                "records": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            }  # type: Dict[str, Any]
            self._loaders[name] = agg
        else:
            agg = existing
        agg["calls"] = int(agg.get("calls") or 0) + 1
        agg["total_s"] = float(agg.get("total_s") or 0.0) + duration
        agg["records"] = int(agg.get("records") or 0) + rows
        if payload.cache_status == "hit":
            agg["cache_hits"] = int(agg.get("cache_hits") or 0) + 1
        elif payload.cache_status == "miss":
            agg["cache_misses"] = int(agg.get("cache_misses") or 0) + 1
        if payload.batch_num is not None:
            entry = self._batch_index.get(int(payload.batch_num))
            if entry is not None:
                loaders = entry["loaders"]  # type: List[Dict[str, Any]]
                loaders.append(
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
        stages_total = dict.fromkeys(_STAGES, 0.0)  # type: Dict[str, float]
        for batch in self._batches:
            batch_stages = batch["stages"]  # type: Dict[str, float]
            for key in _STAGES:
                stages_total[key] += float(batch_stages.get(key, 0.0))
        if not self._batches:
            for entry in self._batch_index.values():
                entry_stages = entry["stages"]  # type: Dict[str, float]
                for key in _STAGES:
                    stages_total[key] += float(entry_stages.get(key, 0.0))
        loaders = []  # type: List[Dict[str, Any]]
        for name in sorted(self._loaders):
            item = dict(self._loaders[name])  # type: Dict[str, Any]
            denom = int(item["cache_hits"]) + int(item["cache_misses"])
            item["cache_hit_rate"] = (int(item["cache_hits"]) / float(denom)) if denom else 0.0
            item["total_s"] = round(float(item["total_s"]), 4)
            loaders.append(item)
        peak_vals = [float(b["rss_mb"]) for b in self._batches if b.get("rss_mb") is not None]
        if end_rss is not None:
            peak_vals.append(float(end_rss))
        if self._pipeline_start_rss is not None:
            peak_vals.append(float(self._pipeline_start_rss))
        demand_id = self._current_demand_id
        end_meta = event.meta  # type: Dict[str, Any]
        for key in ("demand_id", "workflow_node_id", "node_id"):
            raw = end_meta.get(key)
            if raw is not None and str(raw).strip():
                demand_id = str(raw).strip()
                break
        run_id = str(event.run_id or "").strip() or self._current_run_id
        if not demand_id:
            demand_id = run_id
        node = {
            "demand_id": demand_id,
            "run_id": run_id,
            "name": demand_id or run_id,
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
        }  # type: Dict[str, Any]
        self.nodes.append(node)

    def build_run_stats(self, meta=None):
        # type: (Optional[Dict[str, Any]]) -> Dict[str, Any]
        stages_total = dict.fromkeys(_STAGES, 0.0)  # type: Dict[str, float]
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
            pipe = node.get("pipeline") or {}  # type: Dict[str, Any]
            total_rows += int(pipe.get("total_rows_in") or 0)
            total_duration += float(pipe.get("total_duration_s") or 0.0)
            total_batches += int(pipe.get("total_batches") or 0)
            node_stages = node.get("stages_total") or {}  # type: Dict[str, Any]
            for k in _STAGES:
                stages_total[k] += float(node_stages.get(k) or 0.0)
            node_loaders = node.get("loaders") or []  # type: List[Dict[str, Any]]
            for loader in node_loaders:
                name = str(loader.get("name") or "")
                existing = loaders_map.get(name)
                if existing is None:
                    agg = {
                        "name": name,
                        "calls": 0,
                        "total_s": 0.0,
                        "records": 0,
                        "cache_hits": 0,
                        "cache_misses": 0,
                    }  # type: Dict[str, Any]
                    loaders_map[name] = agg
                else:
                    agg = existing
                agg["calls"] = int(agg.get("calls") or 0) + int(loader.get("calls") or 0)
                agg["total_s"] = float(agg.get("total_s") or 0.0) + float(loader.get("total_s") or 0.0)
                agg["records"] = int(agg.get("records") or 0) + int(loader.get("records") or 0)
                agg["cache_hits"] = int(agg.get("cache_hits") or 0) + int(loader.get("cache_hits") or 0)
                agg["cache_misses"] = int(agg.get("cache_misses") or 0) + int(loader.get("cache_misses") or 0)
            outputs.extend(list(node.get("outputs") or []))
            batches.extend(list(node.get("batches") or []))
            mem = node.get("memory") or {}  # type: Dict[str, Any]
            peak_raw = mem.get("peak_mb")
            if peak_raw is not None:
                peak_val = float(peak_raw)
                peak_mb = peak_val if peak_mb is None else max(peak_mb, peak_val)
            start_raw = mem.get("start_mb")
            if start_mb is None and start_raw is not None:
                start_mb = float(start_raw)
            end_raw = mem.get("end_mb")
            if end_raw is not None:
                end_mb = float(end_raw)

        loaders = []  # type: List[Dict[str, Any]]
        for name in sorted(loaders_map):
            item = dict(loaders_map[name])  # type: Dict[str, Any]
            denom = int(item["cache_hits"]) + int(item["cache_misses"])
            item["cache_hit_rate"] = (int(item["cache_hits"]) / float(denom)) if denom else 0.0
            item["total_s"] = round(float(item["total_s"]), 4)
            loaders.append(item)

        def _loader_sort_key(x):
            # type: (Dict[str, Any]) -> float
            return -float(x.get("total_s") or 0.0)

        loaders.sort(key=_loader_sort_key)

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


def resolve_viz_run_dir(observer_or_config):
    # type: (Any) -> Optional[str]
    """Best-effort run directory for a VizObserver / WorkflowVizObserver / VizObserverConfig."""
    config = observer_or_config
    if not hasattr(config, "resolve_output_paths"):
        config = getattr(observer_or_config, "config", None)
    if config is None or not hasattr(config, "resolve_output_paths"):
        return None
    try:
        events_path, snapshot_path, _trace_path = config.resolve_output_paths()
    except Exception:  # noqa: BLE001
        return None
    for path in (snapshot_path, events_path):
        if path:
            parent = os.path.dirname(str(path))
            if parent:
                return parent
    output_dir = getattr(config, "output_dir", None)
    if output_dir:
        return str(output_dir)
    return None


def maybe_auto_write_run_stats_beside_viz(observers, meta=None, extra_run_dirs=None):
    # type: (Any, Optional[Dict[str, Any]], Optional[Any]) -> List[str]
    """When Viz + WorkflowStatsAccumulator coexist, write sibling ``run_stats.json``.

    Does nothing if either side is missing or the accumulator has no ``nodes`` yet.
    Never embeds into ``viz_snapshot.json``.

    ``extra_run_dirs`` MAY list additional directories (e.g. workflow/ overview) to receive
    the same payload once an accumulator is found among ``observers``.
    """
    obs_list = list(observers or [])
    accum = None  # type: Optional[WorkflowStatsAccumulator]
    run_dirs = []  # type: List[str]
    for obs in obs_list:
        if isinstance(obs, WorkflowStatsAccumulator):
            if accum is None or len(getattr(obs, "nodes", None) or []) >= len(getattr(accum, "nodes", None) or []):
                accum = obs
        run_dir = resolve_viz_run_dir(obs)
        if run_dir:
            run_dirs.append(run_dir)
    for extra in list(extra_run_dirs or []):
        if extra:
            run_dirs.append(str(extra))
    if accum is None or not run_dirs:
        return []
    if not list(getattr(accum, "nodes", None) or []):
        return []
    payload = accum.build_run_stats(meta=meta)
    written = []  # type: List[str]
    seen = set()  # type: Set[str]
    for run_dir in run_dirs:
        key = os.path.abspath(str(run_dir))
        if key in seen:
            continue
        seen.add(key)
        written.append(write_run_stats_sibling(run_dir, payload))
    return written


__all__ = (
    "HIGH_IMPACT_OBS_WARNING",
    "SCHEMA_RUN_STATS",
    "RunStatsMeta",
    "WorkflowStatsAccumulator",
    "atomic_write_run_stats_json",
    "maybe_auto_write_run_stats_beside_viz",
    "require_psutil_for_memory",
    "resolve_viz_run_dir",
    "warn_high_impact_observability",
    "write_run_stats_sibling",
)
