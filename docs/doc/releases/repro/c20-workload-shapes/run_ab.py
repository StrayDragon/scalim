#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c20 docs evidence: fuse vs field-major A/B with golden + calc_calls.

Clears plan.late_fields so fusion is measured in the compute segment
(write-only fields would otherwise go to c10 write-precompute).

Outputs: <repo>/.tmp/evidence/c20-perf-report/ + docs-ready summary JSON (rebuildable; not committed)

如何运行（仓库根目录；脚本兼容 Python 3.6+）:

    uv run python docs/doc/releases/repro/c20-workload-shapes/run_ab.py --runs 3

    PYTHONPATH=src .tmp/venvs/py36-scalim/bin/python \\
      docs/doc/releases/repro/c20-workload-shapes/run_ab.py --runs 1

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


def _ensure_src():
    # type: () -> None
    src = os.path.join(_repo_root(), "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _median(xs):
    # type: (List[float]) -> float
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return float(s[mid - 1] + s[mid]) / 2.0


SHAPES = [
    {
        "id": "wide_same_deps_row",
        "label": "宽表同 deps·行",
        "rows": 10000,
        "n_derived": 80,
        "sink": "row",
        "why": "主卖点：大量薄 call_by 共享 (v0,v1)",
    },
    {
        "id": "report_same_deps_row",
        "label": "报表宽派生·行",
        "rows": 20000,
        "n_derived": 48,
        "sink": "row",
        "why": "报表量级行写出 + 同 deps 簇",
    },
    {
        "id": "dense_rows_moderate_row",
        "label": "大行数中等宽·行",
        "rows": 50000,
        "n_derived": 32,
        "sink": "row",
        "why": "行数主导时框架税占比",
    },
    {
        "id": "engine_proxy_flat_row",
        "label": "引擎代理宽表·行",
        "rows": 8000,
        "n_derived": 120,
        "sink": "row",
        "why": "更宽 M，接近规模矩阵 engine 宽度",
    },
    {
        "id": "wide_same_deps_column",
        "label": "宽表同 deps·列（外壳关闭）",
        "rows": 10000,
        "n_derived": 80,
        "sink": "column",
        "why": "列 sink 安全外壳：不融合，对拍仍绿",
    },
    {
        "id": "narrow_same_deps_row",
        "label": "窄表同 deps·行",
        "rows": 40000,
        "n_derived": 4,
        "sink": "row",
        "why": "M 小：加速比通常更温和",
    },
]


def _build_and_run(rows, n_derived, sink_kind, fuse, runs):
    # type: (int, int, str, bool, int) -> Dict[str, Any]
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink, InMemoryRowDataSink
    from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    fields = [
        FieldIr(field_id="id", name="id", source=main, is_primary=True),
        FieldIr(field_id="v0", name="v0", source=main),
        FieldIr(field_id="v1", name="v1", source=main),
    ]  # type: List[Any]
    calcs = {}  # type: Dict[str, Callable[..., Any]]
    targets = ["id", "v0", "v1"]  # type: List[str]
    calc_calls = {"n": 0}

    for i in range(n_derived):
        fid = "d{}".format(i)

        def _make(idx):
            # type: (int) -> Callable[..., Any]
            def _calc(a, b):
                # type: (Any, Any) -> Any
                calc_calls["n"] += 1
                aa = float(a or 0)
                bb = float(b or 0)
                if idx % 3 == 0:
                    return aa + bb + float(idx)
                if idx % 3 == 1:
                    return aa - bb + float(idx)
                return aa * bb + float(idx)

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
        calcs[fid] = _make(i)
        targets.append(fid)

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=targets)
    # Isolate c20 compute-segment fusion (else write-only → late via c10).
    plan.late_fields = ()
    auto_groups = len(plan.compute_fusion_groups)
    if not fuse:
        plan.compute_fusion_groups = ()

    bindings = RuntimeBindings(derived_calculators=calcs)
    data = [{"id": i, "v0": float(i % 97), "v1": float(i % 13)} for i in range(rows)]

    # Golden first 3 rows for fingerprint + full check on last run
    def _expected_row(i):
        # type: (int) -> Dict[str, float]
        v0 = float(i % 97)
        v1 = float(i % 13)
        row = {"id": float(i), "v0": v0, "v1": v1}  # type: Dict[str, float]
        for j in range(n_derived):
            if j % 3 == 0:
                row["d{}".format(j)] = v0 + v1 + float(j)
            elif j % 3 == 1:
                row["d{}".format(j)] = v0 - v1 + float(j)
            else:
                row["d{}".format(j)] = v0 * v1 + float(j)
        return row

    durs = []  # type: List[float]
    last_rows = []  # type: List[Any]
    last_calls = 0
    for _ in range(runs):
        calc_calls["n"] = 0
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=bindings,
            parallel_mode="seq",
            batch_size=min(1000, max(1, rows)),
        )
        t0 = time.perf_counter()
        if sink_kind == "column":
            with InMemoryColumnSink(field_names=targets) as sink:
                engine.run(main_rows=data, sink=sink)
                last_rows = list(sink.get_rows())
        else:
            with InMemoryRowDataSink() as sink:
                engine.run(main_rows=data, sink=sink)
                last_rows = list(sink.get_data())
        durs.append(time.perf_counter() - t0)
        last_calls = calc_calls["n"]

    mismatches = 0
    checked = 0
    for i, got in enumerate(last_rows):
        exp = _expected_row(i)
        for key, ev in exp.items():
            checked += 1
            gv = got.get(key) if isinstance(got, dict) else None
            if float(gv if gv is not None else 0) != float(ev):
                mismatches += 1

    dur = _median(durs)
    return {
        "duration_s_median": dur,
        "duration_s_all": durs,
        "calc_calls": last_calls,
        "expected_calc_calls": rows * n_derived,
        "calc_calls_ok": last_calls == rows * n_derived,
        "golden_ok": mismatches == 0 and checked > 0,
        "value_cells_checked": checked,
        "value_mismatches": mismatches,
        "fusion_groups_planned": auto_groups,
        "fuse": fuse,
        "rows_out": len(last_rows),
        "golden_sample": [_expected_row(i) for i in range(min(2, rows))],
    }


def main():
    # type: () -> None
    _ensure_src()
    parser = argparse.ArgumentParser(description="c20 row-wise fusion A/B (Python 3.6+)")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", type=str, default="")
    parser.add_argument(
        "--rows-scale",
        type=float,
        default=1.0,
        help="multiply each shape's rows by this factor (min 1 row; default 1.0)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=os.path.join(_repo_root(), ".tmp", "evidence", "c20-perf-report"),
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
        n_derived = int(shape["n_derived"])
        sink = str(shape["sink"])
        print("  field_major...", flush=True)
        major = _build_and_run(rows, n_derived, sink, fuse=False, runs=args.runs)
        print("  fused...", flush=True)
        fused = _build_and_run(rows, n_derived, sink, fuse=True, runs=args.runs)
        speedup = None
        if fused["duration_s_median"] > 0:
            speedup = float(major["duration_s_median"]) / float(fused["duration_s_median"])
        case = {
            "id": sid,
            "label": shape["label"],
            "why": shape["why"],
            "params": {
                "rows": rows,
                "rows_base": int(shape["rows"]),
                "rows_scale": float(args.rows_scale),
                "n_derived": n_derived,
                "sink": sink,
            },
            "field_major": major,
            "fused": fused,
            "speedup_major_over_fused": speedup,
            "calc_calls_equal": major["calc_calls"] == fused["calc_calls"],
            "golden_ok_both": bool(major["golden_ok"]) and bool(fused["golden_ok"]),
        }
        cases.append(case)
        print(
            json.dumps(
                {
                    "id": sid,
                    "speedup": speedup,
                    "major_s": major["duration_s_median"],
                    "fused_s": fused["duration_s_median"],
                    "calc_equal": case["calc_calls_equal"],
                    "golden_ok": case["golden_ok_both"],
                    "groups": fused["fusion_groups_planned"],
                    "rows": rows,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    report = {
        "topic": "c20-rowwise-fusion-docs",
        "change": "c20-compute-expr-rowwise-fusion",
        "version": "0.10.0",
        "measured_at": time.strftime("%Y-%m-%d"),
        "python": "{}.{}.{}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2]),
        "rows_scale": float(args.rows_scale),
        "host_note": "合成 workload；本机；清 late_fields 以隔离 compute 段融合；内存 sink + 全表黄金",
        "policy": "auto fusion groups; A/B clears compute_fusion_groups for field-major",
        "cases": cases,
        "summary": {
            "n_cases": len(cases),
            "all_golden_ok": all(c["golden_ok_both"] for c in cases),
            "all_calc_calls_equal": all(c["calc_calls_equal"] for c in cases),
            "speedups": {c["id"]: c["speedup_major_over_fused"] for c in cases},
        },
    }
    path = os.path.join(args.out_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print("report ->", path)


if __name__ == "__main__":
    main()
