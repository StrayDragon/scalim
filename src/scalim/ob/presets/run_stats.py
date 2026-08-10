# pragma: allow-dynattr-file optional-interface: run_stats observes heterogeneous Event payloads and Viz observer configs
# region imports

import json
import os
import warnings
from typing import Any, Dict, List, Optional, Set

from ...events import Event, EventType
from ...vendor.compact.importlibx import import_module
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


def warn_high_impact_observability(kind: str) -> None:
    warnings.warn(HIGH_IMPACT_OBS_WARNING.format(kind=str(kind)), UserWarning, stacklevel=2)


def _rss_mb() -> Optional[float]:
    try:
        psutil = import_module("psutil")
        return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        return None


def _r2(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 2)


def require_psutil_for_memory(reason: str) -> None:
    try:
        _ = import_module("psutil")
    except Exception as exc:
        raise RuntimeError(
            "请求了内存采样({})但 `psutil` 不可用;请安装可选依赖 `psutil`,或使用仅 `duration` 的 `bench`".format(reason)
        ) from exc


@dataclass
class RunStatsMeta:
    profile: Optional[str] = None
    tag: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class WorkflowStatsAccumulator(EventDispatchObserver):
    """累计 `per-pipeline` 快照,避免 `workflow` 共享 `reset` 抹掉证据.

    仅订阅轻量 `EventTypes`(不含 `RELATION_LOOKUP` / `ROW_WRITE` / `FIELD_COMPUTE`).
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

    def __init__(self, sample_rss: bool = False, persist_batches: bool = True) -> None:
        self.event_types = {
            EventType.PIPELINE_START,
            EventType.PIPELINE_END,
            EventType.BATCH_START,
            EventType.BATCH_END,
            EventType.STAGE_SPAN,
            EventType.LOADER_CALL,
            EventType.OUTPUT_TARGET_END,
        }
        self.sample_rss = bool(sample_rss)
        self.persist_batches = bool(persist_batches)
        self.nodes = []
        self._batch_persist_warned = False
        self._reset_current()

    def _reset_current(self) -> None:
        self._pipeline_start_rss = _rss_mb() if self.sample_rss else None
        self._batches = []
        self._batch_index = {}
        self._loaders = {}
        self._outputs = []
        self._total_rows_in = 0
        self._batch_size = None
        self._current_run_id = None
        self._current_demand_id = None

    def on_pipeline_start(self, event: Event) -> None:
        self._reset_current()
        payload = event.payload
        self._batch_size = getattr(payload, "batch_size", None)
        run_id = str(event.run_id or "").strip() or None
        meta: Dict[str, Any] = event.meta
        demand_id: Optional[str] = None
        for key in ("demand_id", "workflow_node_id", "node_id"):
            raw = meta.get(key)
            if raw is not None and str(raw).strip():
                demand_id = str(raw).strip()
                break
        self._current_run_id = run_id
        self._current_demand_id = demand_id or run_id

    def on_batch_start(self, event: Event) -> None:
        payload = event.payload
        try:
            n_rows = len(payload.row_ids or [])
        except TypeError:
            n_rows = 0
        self._total_rows_in += n_rows
        entry: Dict[str, Any] = {
            "n": int(payload.batch_num),
            "duration_s": 0.0,
            "rows_in": n_rows,
            "stages": dict.fromkeys(_STAGES, 0.0),
            "rss_mb": _rss_mb() if self.sample_rss else None,
            "loaders": [],
        }
        self._batch_index[int(payload.batch_num)] = entry
        if self.persist_batches:
            self._batches.append(entry)
            if (not self._batch_persist_warned) and len(self._batches) >= BATCH_PERSIST_WARN_THRESHOLD:
                self._batch_persist_warned = True
                warn_high_impact_observability("persist_batches_large")

    def on_batch_end(self, event: Event) -> None:
        payload = event.payload
        entry = self._batch_index.get(int(payload.batch_num))
        if entry is None:
            return
        entry["duration_s"] = float(payload.duration)
        if self.sample_rss:
            entry["rss_mb"] = _rss_mb()

    def on_stage_span(self, event: Event) -> None:
        payload = event.payload
        entry = self._batch_index.get(int(payload.batch_num))
        if entry is None:
            return
        stage = str(payload.stage)
        stages: Dict[str, float] = entry["stages"]
        if stage in stages:
            stages[stage] += max(0.0, float(payload.duration))

    def on_loader_call(self, event: Event) -> None:
        payload = event.payload
        name = str(payload.loader_name)
        try:
            rows = len(payload.result) if payload.result is not None else 0
        except TypeError:
            rows = 0
        duration = float(payload.duration)
        existing = self._loaders.get(name)
        if existing is None:
            agg: Dict[str, Any] = {
                "name": name,
                "calls": 0,
                "total_s": 0.0,
                "records": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            }
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
                loaders: List[Dict[str, Any]] = entry["loaders"]
                loaders.append(
                    {
                        "name": name,
                        "duration_s": duration,
                        "rows": rows,
                        "cache": payload.cache_status,
                    }
                )

    def on_output_target_end(self, event: Event) -> None:
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

    def on_pipeline_end(self, event: Event) -> None:
        payload = event.payload
        end_rss = _rss_mb() if self.sample_rss else None
        stages_total: Dict[str, float] = dict.fromkeys(_STAGES, 0.0)
        for batch in self._batches:
            batch_stages: Dict[str, float] = batch["stages"]
            for key in _STAGES:
                stages_total[key] += float(batch_stages.get(key, 0.0))
        if not self._batches:
            for entry in self._batch_index.values():
                entry_stages: Dict[str, float] = entry["stages"]
                for key in _STAGES:
                    stages_total[key] += float(entry_stages.get(key, 0.0))
        loaders: List[Dict[str, Any]] = []
        for name in sorted(self._loaders):
            item: Dict[str, Any] = dict(self._loaders[name])
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
        end_meta: Dict[str, Any] = event.meta
        for key in ("demand_id", "workflow_node_id", "node_id"):
            raw = end_meta.get(key)
            if raw is not None and str(raw).strip():
                demand_id = str(raw).strip()
                break
        run_id = str(event.run_id or "").strip() or self._current_run_id
        if not demand_id:
            demand_id = run_id
        node: Dict[str, Any] = {
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
        }
        self.nodes.append(node)

    def build_run_stats(self, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stages_total: Dict[str, float] = dict.fromkeys(_STAGES, 0.0)
        loaders_map: Dict[str, Dict[str, Any]] = {}
        outputs: List[Dict[str, Any]] = []
        batches: List[Dict[str, Any]] = []
        total_rows = 0
        total_duration = 0.0
        total_batches = 0
        peak_mb: Optional[float] = None
        start_mb: Optional[float] = None
        end_mb: Optional[float] = None

        for node in self.nodes:
            pipe: Dict[str, Any] = node.get("pipeline") or {}
            total_rows += int(pipe.get("total_rows_in") or 0)
            total_duration += float(pipe.get("total_duration_s") or 0.0)
            total_batches += int(pipe.get("total_batches") or 0)
            node_stages: Dict[str, Any] = node.get("stages_total") or {}
            for k in _STAGES:
                stages_total[k] += float(node_stages.get(k) or 0.0)
            node_loaders: List[Dict[str, Any]] = node.get("loaders") or []
            for loader in node_loaders:
                name = str(loader.get("name") or "")
                existing = loaders_map.get(name)
                if existing is None:
                    agg: Dict[str, Any] = {
                        "name": name,
                        "calls": 0,
                        "total_s": 0.0,
                        "records": 0,
                        "cache_hits": 0,
                        "cache_misses": 0,
                    }
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
            mem: Dict[str, Any] = node.get("memory") or {}
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

        loaders: List[Dict[str, Any]] = []
        for name in sorted(loaders_map):
            item: Dict[str, Any] = dict(loaders_map[name])
            denom = int(item["cache_hits"]) + int(item["cache_misses"])
            item["cache_hit_rate"] = (int(item["cache_hits"]) / float(denom)) if denom else 0.0
            item["total_s"] = round(float(item["total_s"]), 4)
            loaders.append(item)

        def _loader_sort_key(x: Dict[str, Any]) -> float:
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


def atomic_write_run_stats_json(path: str, payload: Dict[str, Any]) -> str:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    tmp = "{}.tmp.{}".format(path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        _ = handle.write("\n")
    os.replace(tmp, path)
    return path


def write_run_stats_sibling(run_dir: str, payload: Dict[str, Any], filename: str = "run_stats.json") -> str:
    """在 `viz`/`run` 产物目录旁写入 `run_stats` 兄弟文件(非嵌入)."""
    path = os.path.join(str(run_dir), str(filename))
    return atomic_write_run_stats_json(path, payload)


def resolve_viz_run_dir(observer_or_config: Any) -> Optional[str]:
    """尽力解析 `VizObserver` / `WorkflowVizObserver` / `VizObserverConfig` 的 `run` 目录."""
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


def maybe_auto_write_run_stats_beside_viz(
    observers: Any,
    meta: Optional[Dict[str, Any]] = None,
    extra_run_dirs: Optional[Any] = None,
) -> List[str]:
    """当 `Viz` 与 `WorkflowStatsAccumulator` 并存时,写兄弟 `run_stats.json`.

    任一侧缺失,或累计器尚无 `nodes` 时不做任何事.
    永不嵌入 `viz_snapshot.json`.

    `extra_run_dirs` `MAY` 列出额外目录(例如 `workflow`/`overview`)以在找到累计器后接收同一载荷.
    """
    obs_list = list(observers or [])
    accum: Optional[WorkflowStatsAccumulator] = None
    run_dirs: List[str] = []
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
    written: List[str] = []
    seen: Set[str] = set()
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
