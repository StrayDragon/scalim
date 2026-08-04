"""本地 RSS 增量代理对比：跑 naive vs Scalim，可选刷新 chart_snapshot。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from notebooks.marimo.example_readme_suite.support import knobs
from notebooks.marimo.example_readme_suite.support.naive_baseline import run_naive
from notebooks.marimo.example_readme_suite.support.scalim_path import run_scalim

SNAPSHOT_NAME = "chart_snapshot.json"


def snapshot_path() -> Path:
    return Path(__file__).resolve().parent / SNAPSHOT_NAME


def relative_ratio(naive_delta: int, scalim_delta: int) -> Dict[str, float]:
    naive_v = float(max(1, int(naive_delta)))
    scalim_v = float(max(0, int(scalim_delta)))
    return {
        "naive_rel": 1.0,
        "scalim_rel": round(scalim_v / naive_v, 4),
    }


def run_compare() -> Dict[str, Any]:
    naive = run_naive()
    scalim = run_scalim()
    assert int(naive["rows"]) == int(scalim["rows"]) == int(knobs.N_ROWS)
    ratios = relative_ratio(int(naive["rss_kb_delta"]), int(scalim["rss_kb_delta"]))
    return {
        "knobs": knobs.effective_knobs(),
        "naive": {k: naive[k] for k in ("rows", "rss_kb_delta", "label") if k in naive},
        "scalim": {k: scalim[k] for k in ("rows", "rss_kb_delta", "label") if k in scalim},
        "ratios": ratios,
    }


def load_snapshot() -> Dict[str, Any]:
    path = snapshot_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("chart_snapshot.json must be an object")
    return payload


def write_snapshot_from_live(compare: Dict[str, Any]) -> Path:
    """本地可选：用本机运行前后 RSS 增量比重写 snapshot（不进 CI 硬闸）。"""
    payload = {
        "knobs": compare["knobs"],
        "ratios": compare["ratios"],
        "measurement": "Before/after local RSS delta proxy; not a sampled peak.",
        "note": "Illustrative relative local RSS deltas from a local run; CI does not hard-gate these numbers.",
    }
    path = snapshot_path()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
