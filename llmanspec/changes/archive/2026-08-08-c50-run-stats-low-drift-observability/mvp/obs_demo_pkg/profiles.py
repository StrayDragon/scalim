# -*- coding: utf-8 -*-
"""Observer profile factories (dev-only).

Prefer framework ``build_observability_profile`` for baseline/bench/bench_plus/debug;
keep local extras for probe / ExecutionTrace.
"""
from __future__ import print_function

import os
import warnings
from typing import Any, Dict, List, Optional

from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.ob.presets.profiles import ObservabilityProfile, build_observability_profile
from scalim.ob.presets.relations import RelationConfig, RelationObserver
from scalim.ob.presets.run_stats import require_psutil_for_memory
from scalim.ob.presets.viz import VizObserverConfig


def build_profile(name, run_dir, sampling_interval=1):
    # type: (str, str, int) -> Dict[str, Any]
    name = str(name or "baseline").strip().lower()
    env = {}  # type: Dict[str, Optional[str]]

    if name == "probe":
        # Probe = bench + env knobs (framework bench does not set env).
        built = build_observability_profile(
            ObservabilityProfile.BENCH,
            sampling_interval=int(sampling_interval),
            include_memory=True,
            persist_batches=True,
        )
        env["SCALIM_PROBE_CALL_BY_DEP_CARDINALITY"] = "4096"
        meta = dict(built.get("meta") or {})
        meta["profile"] = "probe"
        meta.setdefault("collectors", [])
        if "SCALIM_PROBE_CALL_BY_DEP_CARDINALITY" not in meta["collectors"]:
            meta["collectors"] = list(meta["collectors"]) + ["SCALIM_PROBE_CALL_BY_DEP_CARDINALITY"]
        return {
            "name": "probe",
            "components": list(built["components"]),
            "handles": dict(built["handles"]),
            "viz_config": built.get("viz_config"),
            "env": env,
            "meta": meta,
            "events_expected": _events_for("bench"),
        }

    if name == "baseline":
        built = build_observability_profile(ObservabilityProfile.BASELINE)
        return {
            "name": name,
            "components": [],
            "handles": dict(built["handles"]),
            "viz_config": None,
            "env": env,
            "meta": dict(built.get("meta") or {"profile": "baseline"}),
            "events_expected": [],
        }

    if name not in ("bench", "bench_plus", "debug"):
        raise ValueError("unknown profile {!r}".format(name))

    include_memory = name in ("bench", "bench_plus", "debug")
    if include_memory:
        require_psutil_for_memory("obs-demo profile={}".format(name))

    viz_dir = os.path.join(run_dir, "viz") if name == "debug" else None
    # Framework debug already warns; catch so matrix run is not noisy as error.
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        built = build_observability_profile(
            name,
            sampling_interval=int(sampling_interval),
            include_memory=bool(include_memory),
            viz_output_dir=viz_dir,
            persist_batches=True,
        )

    # Demo historically also mounted ExecutionTrace on debug.
    if name == "debug":
        components = list(built["components"])
        handles = dict(built["handles"])
        if handles.get("relation") is None:
            components.append(
                RelationObserver(
                    config=RelationConfig(
                        enabled=True,
                        sampling_rate=0.05,
                        max_samples=2000,
                        report_format="none",
                        include_details=True,
                    )
                )
            )
        trace = ExecutionTraceObserver()
        components.append(trace)
        handles["trace"] = trace
        meta = dict(built.get("meta") or {})
        meta.setdefault("collectors", [])
        meta["collectors"] = list(meta["collectors"]) + ["ExecutionTraceObserver"]
        viz_config = built.get("viz_config")
        if viz_config is None and viz_dir:
            viz_config = VizObserverConfig(
                output_dir=viz_dir,
                trace_enabled=False,
                payload_policy="summary",
                append=False,
                run_name="obs-demo-debug",
                env="dev",
            )
        return {
            "name": name,
            "components": components,
            "handles": handles,
            "viz_config": viz_config,
            "env": env,
            "meta": meta,
            "events_expected": _events_for(name),
        }

    return {
        "name": name,
        "components": list(built["components"]),
        "handles": dict(built["handles"]),
        "viz_config": built.get("viz_config"),
        "env": env,
        "meta": dict(built.get("meta") or {}),
        "events_expected": _events_for(name),
    }


def _events_for(name):
    # type: (str) -> List[str]
    if name == "baseline":
        return []
    base = [
        "PIPELINE_START",
        "PIPELINE_END",
        "BATCH_START",
        "BATCH_END",
        "STAGE_SPAN",
        "LOADER_CALL",
        "OUTPUT_TARGET_END",
    ]
    if name == "debug":
        base = base + ["RELATION_LOOKUP", "OPERATOR_SPAN"]
    return base


def apply_env(env_map):
    # type: (Dict[str, Optional[str]]) -> Dict[str, Optional[str]]
    prev = {}  # type: Dict[str, Optional[str]]
    for key, value in (env_map or {}).items():
        prev[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
    return prev


def restore_env(prev):
    # type: (Dict[str, Optional[str]]) -> None
    for key, value in (prev or {}).items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
