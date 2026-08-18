#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Workload-shaped A/B for c10 write-precompute (evidence for 0.10.0 docs).

Shapes use counts only (no business field names). Each case:
  - flat write-only derived (v0,v1 -> d*) + optional late→late chain (v0 -> c0 -> ...)
  - engine A/B: auto late_fields vs forced empty late_fields
  - memory sink + on-the-fly golden check
  - residency sim peaks (eager full-hold vs late scratch)

Output: <repo>/.tmp/evidence/c10-perf-report/workload-shapes/result.json (rebuildable; not committed)

如何运行（仓库根目录；脚本兼容 Python 3.6+）:

    # 开发环境
    uv run python docs/doc/releases/repro/c10-workload-shapes/run_ab.py --runs 3

    # Python 3.6 运行时边界复现（本仓库 .tmp/venvs/py36-scalim）
    PYTHONPATH=src .tmp/venvs/py36-scalim/bin/python \\
      docs/doc/releases/repro/c10-workload-shapes/run_ab.py --runs 1

    # 缩小行数做冒烟（仍跑完整 shape 集合）
    .../run_ab.py --runs 1 --rows-scale 0.25
"""

from __future__ import absolute_import, print_function

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


def _repo_root():
    # type: () -> str
    # Walk up until we find the repo root (pyproject.toml + src/), so this
    # script works from any checkout depth (e.g. docs/doc/releases/repro/...).
    here = os.path.abspath(os.path.dirname(__file__))
    cur = here
    while cur != os.path.dirname(cur):
        if os.path.isfile(os.path.join(cur, "pyproject.toml")) and os.path.isdir(os.path.join(cur, "src")):
            return cur
        cur = os.path.dirname(cur)
    return here


def _ensure_src_path():
    # type: () -> None
    src = os.path.join(_repo_root(), "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _rss_kb():
    # type: () -> int
    try:
        with open("/proc/self/statm", "r") as f:
            parts = f.read().strip().split()
        return int(int(parts[1]) * os.sysconf("SC_PAGE_SIZE") / 1024)
    except Exception:
        return 0


def _median(xs):
    # type: (List[float]) -> float
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return float(s[mid - 1] + s[mid]) / 2.0


def expected_flat(v0, v1, idx):
    # type: (float, float, int) -> float
    if idx % 3 == 0:
        return v0 + v1
    if idx % 3 == 1:
        return v0 - v1
    return v0 * v1


def expected_chain(v0, depth_idx):
    # type: (float, int) -> float
    return v0 + float(depth_idx + 1)


def golden_table(rows, n_flat, chain_depth):
    # type: (int, int, int) -> List[Dict[str, float]]
    out = []  # type: List[Dict[str, float]]
    for i in range(rows):
        v0 = float(i % 97)
        v1 = float(i % 13)
        row = {"id": float(i), "v0": v0, "v1": v1}  # type: Dict[str, float]
        for j in range(n_flat):
            row["d{}".format(j)] = expected_flat(v0, v1, j)
        for k in range(chain_depth):
            row["c{}".format(k)] = expected_chain(v0, k)
        out.append(row)
    return out


def sim_peaks(rows, n_flat, chain_depth, sink):
    # type: (int, int, int, str) -> Dict[str, Any]
    n_derived = n_flat + chain_depth
    eager = rows * n_derived
    if sink == "row":
        late = max(n_derived, 1)
    else:
        # column: retain chain prefix until dependents written; flat columns ~1 at a time
        late = rows * max(chain_depth, 1) if chain_depth else rows
    return {
        "peak_derived_cells_eager": eager,
        "peak_derived_cells_late": late,
        "peak_ratio_eager_over_late": float(eager) / float(late),
        "est_eager_hold_gib": eager * 64.0 / (1024.0**3),
        "est_late_scratch_gib": late * 64.0 / (1024.0**3),
    }


SHAPES = [
    # report-like: dozens of export cols + short late→late chain
    {
        "id": "report_mixed_row",
        "label": "报表混合·行写出",
        "rows": 20000,
        "flat_fields": 48,
        "chain_depth": 8,
        "sink": "row",
        "why": "接近多列导出 + 少量链式派生的报表 demand",
    },
    {
        "id": "report_mixed_column",
        "label": "报表混合·列写出",
        "rows": 20000,
        "flat_fields": 48,
        "chain_depth": 8,
        "sink": "column",
        "why": "同 shape，列 sink（驻留叙事更强）",
    },
    # wide flat export
    {
        "id": "wide_export_row",
        "label": "宽表纯导出·行",
        "rows": 10000,
        "flat_fields": 80,
        "chain_depth": 0,
        "sink": "row",
        "why": "大量只写出 flat 派生，晚算主收益区",
    },
    {
        "id": "wide_export_column",
        "label": "宽表纯导出·列",
        "rows": 10000,
        "flat_fields": 80,
        "chain_depth": 0,
        "sink": "column",
        "why": "宽表列路径墙钟 + 峰值列驻留",
    },
    # deeper chain (late→late)
    {
        "id": "chain_export_row",
        "label": "链式派生·行",
        "rows": 30000,
        "flat_fields": 4,
        "chain_depth": 24,
        "sink": "row",
        "why": "late→late 链在行路径按行局部物化",
    },
    # engine-proxy width (from scale matrix width_mode=engine flat)
    {
        "id": "engine_proxy_flat_row",
        "label": "引擎代理宽表·行",
        "rows": 8000,
        "flat_fields": 120,
        "chain_depth": 0,
        "sink": "row",
        "why": "对齐规模矩阵 engine width 量级（可本地分钟级跑完）",
    },
    # denser rows, moderate width
    {
        "id": "dense_rows_moderate_row",
        "label": "大行数中等宽·行",
        "rows": 50000,
        "flat_fields": 32,
        "chain_depth": 4,
        "sink": "row",
        "why": "行数主导时框架税 vs 写出派生比",
    },
]


def _build_engine(rows, n_flat, chain_depth, sink_kind, late):
    # type: (int, int, int, str, bool) -> Callable[[], Dict[str, Any]]
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    fields = [
        FieldIr(field_id="id", name="id", source_id=main.source_id, is_primary=True),
        FieldIr(field_id="v0", name="v0", source_id=main.source_id),
        FieldIr(field_id="v1", name="v1", source_id=main.source_id),
    ]  # type: List[Any]
    calcs = {}  # type: Dict[str, Callable[..., Any]]
    targets = ["id", "v0", "v1"]  # type: List[str]
    calc_calls = {"n": 0}

    for i in range(n_flat):
        fid = "d{}".format(i)

        def _make_flat(idx):
            # type: (int) -> Callable[..., Any]
            def _calc(a, b):
                # type: (Any, Any) -> Any
                calc_calls["n"] += 1
                return expected_flat(float(a or 0), float(b or 0), idx)

            return _calc

        fields.append(
            DerivedFieldIr(
                field_id=fid,
                name=fid,
                dependencies=("v0", "v1"),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id="{}.calculator".format(fid)),
                    args=(
                        CallByValueIr(kind="field", value="v0"),
                        CallByValueIr(kind="field", value="v1"),
                    ),
                ),
            )
        )
        calcs[fid] = _make_flat(i)
        targets.append(fid)

    prev = "v0"
    for k in range(chain_depth):
        fid = "c{}".format(k)
        dep = prev

        def _make_chain(_depth_idx):
            # type: (int) -> Callable[..., Any]
            def _calc(x):
                # type: (Any) -> Any
                calc_calls["n"] += 1
                return float(x or 0) + 1.0

            return _calc

        fields.append(
            DerivedFieldIr(
                field_id=fid,
                name=fid,
                dependencies=(dep,),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id="{}.calculator".format(fid)),
                    args=(CallByValueIr(kind="field", value=dep),),
                ),
            )
        )
        calcs[fid] = _make_chain(k)
        targets.append(fid)
        prev = fid

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=targets)
    auto_late = tuple(plan.late_fields)
    if not late:
        plan.late_fields = ()
    bindings = RuntimeBindings(derived_calculators=calcs)
    data = [{"id": i, "v0": float(i % 97), "v1": float(i % 13)} for i in range(rows)]
    # sample golden check (all rows) — memory OK for these shapes
    golden = golden_table(rows, n_flat, chain_depth)

    def _run():
        # type: () -> Dict[str, Any]
        calc_calls["n"] = 0
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=bindings,
            parallel_mode="seq",
            batch_size=min(500, max(1, rows)),
        )
        mismatches = 0
        checked = 0
        got_rows = []  # type: List[Any]

        if sink_kind == "row":
            from scalim.sinks.memory import InMemoryRowDataSink

            with InMemoryRowDataSink() as sink:
                engine.run(main_rows=data, sink=sink)
                got_rows = list(sink.get_data())
        else:
            from scalim.sinks.memory import InMemoryColumnSink

            with InMemoryColumnSink(field_names=targets) as sink:
                engine.run(main_rows=data, sink=sink)
                got_rows = list(sink.get_rows())

        for g, e in zip(got_rows, golden):
            for key in e:
                checked += 1
                gv = g.get(key) if isinstance(g, dict) else None
                if float(gv if gv is not None else 0) != float(e[key]):
                    mismatches += 1

        return {
            "rows": rows,
            "n_flat": n_flat,
            "chain_depth": chain_depth,
            "sink": sink_kind,
            "late": late,
            "late_fields": len(auto_late) if late else 0,
            "auto_late_fields": len(auto_late),
            "calc_calls": calc_calls["n"],
            "value_cells_checked": checked,
            "value_mismatches": mismatches,
            "golden_ok": mismatches == 0 and checked > 0,
            "got_row_count": len(got_rows),
        }

    return _run


def _run_timed(fn, runs):
    # type: (Callable[[], Any], int) -> Dict[str, Any]
    durs = []  # type: List[float]
    meta = {}  # type: Dict[str, Any]
    rss0 = _rss_kb()
    rss_peak = rss0
    for _ in range(runs):
        t0 = time.perf_counter()
        meta = fn() or {}
        durs.append(time.perf_counter() - t0)
        rss_peak = max(rss_peak, _rss_kb())
    rss1 = _rss_kb()
    dur = _median(durs)
    rows = int(meta.get("rows") or 0)
    return {
        "duration_s_median": dur,
        "duration_s_all": durs,
        "rss_kb_before": rss0,
        "rss_kb_after": rss1,
        "rss_kb_peak_approx": rss_peak,
        "delta_rss_kb": rss1 - rss0,
        "rows": rows,
        "rows_per_s": (float(rows) / dur) if dur > 0 and rows else None,
        "meta": meta,
    }


def main():
    # type: () -> None
    _ensure_src_path()
    parser = argparse.ArgumentParser(description="c10 workload-shaped A/B (Python 3.6+)")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", type=str, default="", help="comma-separated shape ids")
    parser.add_argument(
        "--rows-scale",
        type=float,
        default=1.0,
        help="multiply each shape's rows by this factor (min 1 row; default 1.0)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=os.path.join(_repo_root(), ".tmp", "evidence", "c10-perf-report", "workload-shapes"),
    )
    args = parser.parse_args()

    if float(args.rows_scale) <= 0:
        raise SystemExit("--rows-scale must be > 0")

    only = set([x.strip() for x in args.only.split(",") if x.strip()]) if args.only else None
    shapes = [s for s in SHAPES if only is None or s["id"] in only]
    os.makedirs(args.out_dir, exist_ok=True)

    cases = []  # type: List[Dict[str, Any]]
    for shape in shapes:
        sid = shape["id"]
        print("==> {}".format(sid), flush=True)
        rows = max(1, int(round(float(shape["rows"]) * float(args.rows_scale))))
        n_flat = int(shape["flat_fields"])
        chain = int(shape["chain_depth"])
        sink = str(shape["sink"])

        print("  eager...", flush=True)
        eager = _run_timed(_build_engine(rows, n_flat, chain, sink, late=False), args.runs)
        print("  late...", flush=True)
        late = _run_timed(_build_engine(rows, n_flat, chain, sink, late=True), args.runs)

        e_dur = float(eager["duration_s_median"])
        l_dur = float(late["duration_s_median"])
        speedup = (e_dur / l_dur) if l_dur > 0 else None
        e_calls = eager["meta"].get("calc_calls")
        l_calls = late["meta"].get("calc_calls")
        sim = sim_peaks(rows, n_flat, chain, sink)

        case = {
            "id": sid,
            "label": shape["label"],
            "why": shape["why"],
            "params": {
                "rows": rows,
                "rows_base": int(shape["rows"]),
                "rows_scale": float(args.rows_scale),
                "flat_fields": n_flat,
                "chain_depth": chain,
                "sink": sink,
                "derived_fields": n_flat + chain,
            },
            "engine_eager": eager,
            "engine_late": late,
            "speedup_eager_over_late": speedup,
            "calc_calls_equal": e_calls == l_calls,
            "golden_ok_both": bool(eager["meta"].get("golden_ok")) and bool(late["meta"].get("golden_ok")),
            "sim_residency": sim,
        }
        cases.append(case)
        print(
            json.dumps(
                {
                    "id": sid,
                    "speedup": speedup,
                    "eager_s": e_dur,
                    "late_s": l_dur,
                    "calc_equal": e_calls == l_calls,
                    "golden_ok": case["golden_ok_both"],
                    "late_fields": late["meta"].get("late_fields"),
                    "peak_ratio": sim["peak_ratio_eager_over_late"],
                    "rows": rows,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    report = {
        "topic": "c10-workload-shapes",
        "change": "c10-write-precompute-derived-fields",
        "purpose": "0.10.0 human-docs evidence: report-like / wide / chain shapes",
        "python": "{}.{}.{}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2]),
        "runs": args.runs,
        "rows_scale": float(args.rows_scale),
        "policy": "auto-late via existing deps; A/B clears late_fields for eager",
        "cases": cases,
        "summary": {
            "n_cases": len(cases),
            "all_golden_ok": all(c["golden_ok_both"] for c in cases),
            "all_calc_calls_equal": all(c["calc_calls_equal"] for c in cases),
            "speedups": {c["id"]: c["speedup_eager_over_late"] for c in cases},
        },
    }
    path = os.path.join(args.out_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("report ->", path)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
