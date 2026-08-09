# -*- coding: utf-8 -*-
"""JSON collectors: wall / run_stats projection / output fingerprint.

Workflow-aware: shared observers reset per demand pipeline; we snapshot on
each PIPELINE_END into nodes[] so detail stats are not lost to metrics.
"""

from __future__ import print_function

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Set

from scalim.events import Event, EventType
from scalim.ob.observer import EventDispatchObserver


def rss_mb():
    # type: () -> Optional[float]
    try:
        import psutil  # type: ignore

        return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
    except Exception:
        return None


def atomic_write_json(path, payload):
    # type: (str, Dict[str, Any]) -> str
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    tmp = path + ".tmp.{}".format(os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    os.replace(tmp, path)
    return path


class WorkflowStatsAccumulator(EventDispatchObserver):
    """Accumulate per-pipeline snapshots (survives PerformanceObserver resets)."""

    event_types = {
        EventType.PIPELINE_START,
        EventType.PIPELINE_END,
        EventType.BATCH_START,
        EventType.BATCH_END,
        EventType.STAGE_SPAN,
        EventType.LOADER_CALL,
        EventType.OUTPUT_TARGET_END,
    }  # type: Set[EventType]

    def __init__(self, sample_rss=True):
        # type: (bool) -> None
        self.sample_rss = bool(sample_rss)
        self.nodes = []  # type: List[Dict[str, Any]]
        self._reset_current()

    def _reset_current(self):
        # type: () -> None
        self._started_at = time.time()
        self._pipeline_start_rss = rss_mb() if self.sample_rss else None
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
            "stages": {"stream": 0.0, "loader": 0.0, "compute": 0.0, "write": 0.0},
            "rss_mb": rss_mb() if self.sample_rss else None,
            "loaders": [],
        }
        self._batch_index[int(payload.batch_num)] = entry
        self._batches.append(entry)

    def on_batch_end(self, event):
        # type: (Event) -> None
        payload = event.payload
        entry = self._batch_index.get(int(payload.batch_num))
        if entry is None:
            return
        entry["duration_s"] = float(payload.duration)
        if self.sample_rss:
            entry["rss_mb"] = rss_mb()

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
        end_rss = rss_mb() if self.sample_rss else None
        stages_total = {"stream": 0.0, "loader": 0.0, "compute": 0.0, "write": 0.0}
        for batch in self._batches:
            for key in stages_total:
                stages_total[key] += float(batch["stages"].get(key, 0.0))
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
                "total_batches": int(getattr(payload, "total_batches", len(self._batches)) or len(self._batches)),
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
            "batches": list(self._batches),
            "loaders": loaders,
            "outputs": list(self._outputs),
        }
        self.nodes.append(node)


def _r2(value):
    # type: (Optional[float]) -> Optional[float]
    return None if value is None else round(float(value), 2)


def build_run_stats(accumulator, perf_observer=None, meta=None):
    # type: (Any, Any, Optional[Dict[str, Any]]) -> Dict[str, Any]
    # Prefer framework WorkflowStatsAccumulator.build_run_stats (scalim_run_stats/v1).
    if accumulator is not None and hasattr(accumulator, "build_run_stats"):
        payload = accumulator.build_run_stats(meta=meta)
        if perf_observer is not None:
            metrics = perf_observer.get_metrics() if hasattr(perf_observer, "get_metrics") else None
            if metrics is not None:
                payload = dict(payload)
                payload["perf_last_pipeline"] = metrics.to_dict()
        return payload

    nodes = list(accumulator.nodes) if accumulator is not None else []

    # Aggregate across workflow nodes for top-level convenience.
    stages_total = {"stream": 0.0, "loader": 0.0, "compute": 0.0, "write": 0.0}
    loaders_map = {}  # type: Dict[str, Dict[str, Any]]
    outputs = []  # type: List[Dict[str, Any]]
    batches = []  # type: List[Dict[str, Any]]
    total_rows = 0
    total_duration = 0.0
    total_batches = 0
    peak_mb = None  # type: Optional[float]
    start_mb = None  # type: Optional[float]
    end_mb = None  # type: Optional[float]

    for node in nodes:
        pipe = node.get("pipeline") or {}
        total_rows += int(pipe.get("total_rows_in") or 0)
        total_duration += float(pipe.get("total_duration_s") or 0.0)
        total_batches += int(pipe.get("total_batches") or 0)
        for k in stages_total:
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
        # Prefix batch index with node ordinal for uniqueness in flat view.
        node_i = len([b for b in batches if True])  # placeholder
        _ = node_i
        for b in node.get("batches") or []:
            batches.append(b)
        mem = node.get("memory") or {}
        for key, slot in (("peak_mb", "peak"), ("start_mb", "start"), ("end_mb", "end")):
            val = mem.get(key)
            if val is None:
                continue
            if key == "peak_mb":
                peak_mb = val if peak_mb is None else max(peak_mb, float(val))
            elif key == "start_mb" and start_mb is None:
                start_mb = float(val)
            elif key == "end_mb":
                end_mb = float(val)

    loaders = []
    for name in sorted(loaders_map):
        item = dict(loaders_map[name])
        denom = item["cache_hits"] + item["cache_misses"]
        item["cache_hit_rate"] = (item["cache_hits"] / float(denom)) if denom else 0.0
        item["total_s"] = round(float(item["total_s"]), 4)
        loaders.append(item)
    loaders.sort(key=lambda x: -float(x.get("total_s") or 0.0))

    perf_dict = None
    if perf_observer is not None:
        metrics = perf_observer.get_metrics() if hasattr(perf_observer, "get_metrics") else None
        if metrics is not None:
            perf_dict = metrics.to_dict()

    return {
        "schema": "scalim_obs_demo_run_stats/v0",
        "meta": dict(meta or {}),
        "pipeline": {
            "total_duration_s": round(total_duration, 4),
            "total_batches": int(total_batches),
            "total_rows_in": int(total_rows),
            "throughput_rows_s": round(total_rows / total_duration, 2) if total_duration > 0 else None,
            "node_count": len(nodes),
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
        "nodes": nodes,
        "refs": {"perf_last_pipeline": perf_dict},
    }


def fingerprint_path(path, max_bytes=2 * 1024 * 1024):
    # type: (str, int) -> Dict[str, Any]
    info = {"path": path, "exists": False, "size": 0, "sha256_head": None}  # type: Dict[str, Any]
    if not path or not os.path.isfile(path):
        return info
    size = os.path.getsize(path)
    info["exists"] = True
    info["size"] = int(size)
    h = hashlib.sha256()
    remaining = int(max_bytes)
    with open(path, "rb") as handle:
        while remaining > 0:
            chunk = handle.read(min(65536, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    info["sha256_head"] = h.hexdigest()
    info["hashed_bytes"] = min(size, max_bytes)
    return info


def wall_payload(profile, elapsed_s, exit_code=0, extras=None):
    # type: (str, float, int, Optional[Dict[str, Any]]) -> Dict[str, Any]
    payload = {
        "profile": profile,
        "elapsed_s": round(float(elapsed_s), 4),
        "rss_mb_end": rss_mb(),
        "exit_code": int(exit_code),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }  # type: Dict[str, Any]
    if extras:
        payload.update(extras)
    return payload
