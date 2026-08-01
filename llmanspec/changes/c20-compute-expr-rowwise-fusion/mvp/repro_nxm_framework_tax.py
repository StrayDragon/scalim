#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c20 MVP: illustrate N*M framework tax for thin call_by with shared deps.

Does NOT implement engine fusion. Measures:
  - ScalimEngine wide vs narrow shapes (current behavior)
  - Pure-Python micro loops: field-major vs row-wise dep loads (intuition upper bound)

Outputs evidence under ./evidence/<timestamp>/result.json (next to this file).
"""

from __future__ import absolute_import, print_function

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Tuple


def _repo_root():
    # type: () -> str
    here = os.path.abspath(os.path.dirname(__file__))
    # .../llmanspec/changes/c20-.../mvp -> repo root = 4 levels up
    return os.path.abspath(os.path.join(here, "..", "..", "..", ".."))


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


def _run_timed(fn, runs):
    # type: (Callable[[], Any], int) -> Dict[str, Any]
    durs = []  # type: List[float]
    meta = {}  # type: Dict[str, Any]
    rss0 = _rss_kb()
    for _ in range(runs):
        t0 = time.perf_counter()
        meta = fn() or {}
        durs.append(time.perf_counter() - t0)
    rss1 = _rss_kb()
    dur = _median(durs)
    rows = int(meta.get("rows") or 0)
    fields = int(meta.get("fields") or 0)
    return {
        "duration_s_median": dur,
        "duration_s_all": durs,
        "rss_kb_before": rss0,
        "rss_kb_after": rss1,
        "delta_rss_kb": rss1 - rss0,
        "rows": rows,
        "fields": fields,
        "rows_per_s": (float(rows) / dur) if dur > 0 and rows else None,
        "calc_calls": meta.get("calc_calls"),
        "dep_reads": meta.get("dep_reads"),
        "meta": meta,
    }


def _build_engine_case(rows, n_derived):
    # type: (int, int) -> Tuple[Callable[[], Dict[str, Any]], Dict[str, int]]
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryRowDataSink
    from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

    counters = {"calc_calls": 0}  # type: Dict[str, int]
    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    fields = [
        FieldIr(field_id="id", name="id", source=main, is_primary=True),
        FieldIr(field_id="v0", name="v0", source=main),
        FieldIr(field_id="v1", name="v1", source=main),
    ]  # type: List[Any]
    calcs = {}  # type: Dict[str, Callable[..., Any]]
    targets = ["id"]  # type: List[str]

    def _make_calc(kind):
        # type: (int) -> Callable[..., Any]
        def _calc(a, b):
            # type: (Any, Any) -> Any
            counters["calc_calls"] += 1
            aa = a or 0
            bb = b or 0
            if kind % 3 == 0:
                return aa + bb
            if kind % 3 == 1:
                return aa - bb
            return aa * bb

        return _calc

    for i in range(n_derived):
        fid = "d{}".format(i)
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
        calcs[fid] = _make_calc(i)
        targets.append(fid)

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=targets)
    bindings = RuntimeBindings(derived_calculators=calcs)
    data = [{"id": i, "v0": float(i % 97), "v1": float(i % 13)} for i in range(rows)]

    def _run():
        # type: () -> Dict[str, Any]
        counters["calc_calls"] = 0
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=bindings,
            parallel_mode="seq",
            batch_size=200,
        )
        with InMemoryRowDataSink() as sink:
            engine.run(main_rows=data, sink=sink)
        return {
            "rows": rows,
            "fields": n_derived,
            "calc_calls": counters["calc_calls"],
            "expected_calc_calls": rows * n_derived,
            "shape": "engine_call_by",
        }

    return _run, counters


def _micro_field_major(rows, n_fields, deps_per_field):
    # type: (int, int, int) -> Dict[str, Any]
    """Simulate field-major: for each field, for each row, read deps then thin calc."""
    table = [[float((r + c) % 97) for c in range(deps_per_field)] for r in range(rows)]
    dep_reads = 0
    calc_calls = 0
    out = [[0.0] * n_fields for _ in range(rows)]
    for f in range(n_fields):
        for r in range(rows):
            acc = 0.0
            for d in range(deps_per_field):
                dep_reads += 1
                acc += table[r][d]
            calc_calls += 1
            out[r][f] = acc + float(f)
    return {
        "rows": rows,
        "fields": n_fields,
        "dep_reads": dep_reads,
        "calc_calls": calc_calls,
        "checksum": sum(sum(row) for row in out),
        "shape": "micro_field_major",
    }


def _micro_row_wise(rows, n_fields, deps_per_field):
    # type: (int, int, int) -> Dict[str, Any]
    """Simulate row-wise same-deps fusion: read deps once per row, then M thin calcs."""
    table = [[float((r + c) % 97) for c in range(deps_per_field)] for r in range(rows)]
    dep_reads = 0
    calc_calls = 0
    out = [[0.0] * n_fields for _ in range(rows)]
    for r in range(rows):
        deps = []
        for d in range(deps_per_field):
            dep_reads += 1
            deps.append(table[r][d])
        base = sum(deps)
        for f in range(n_fields):
            calc_calls += 1
            out[r][f] = base + float(f)
    return {
        "rows": rows,
        "fields": n_fields,
        "dep_reads": dep_reads,
        "calc_calls": calc_calls,
        "checksum": sum(sum(row) for row in out),
        "shape": "micro_row_wise",
    }


def main():
    # type: () -> None
    _ensure_src_path()
    parser = argparse.ArgumentParser(description="c20 N*M framework-tax MVP")
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--wide-fields", type=int, default=40)
    parser.add_argument("--narrow-fields", type=int, default=2)
    parser.add_argument("--deps", type=int, default=2)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out-dir", type=str, default="")
    args = parser.parse_args()

    here = os.path.abspath(os.path.dirname(__file__))
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir or os.path.join(here, "evidence", ts)
    os.makedirs(out_dir, exist_ok=True)

    results = {}  # type: Dict[str, Any]

    print("==> engine wide_many_call_by", flush=True)
    wide_fn, _ = _build_engine_case(args.rows, args.wide_fields)
    results["engine_wide_many_call_by"] = _run_timed(wide_fn, args.runs)

    print("==> engine narrow_few_call_by", flush=True)
    narrow_fn, _ = _build_engine_case(args.rows, args.narrow_fields)
    results["engine_narrow_few_call_by"] = _run_timed(narrow_fn, args.runs)

    print("==> micro field_major", flush=True)
    results["micro_field_major"] = _run_timed(
        lambda: _micro_field_major(args.rows, args.wide_fields, args.deps), args.runs
    )
    print("==> micro row_wise", flush=True)
    results["micro_row_wise"] = _run_timed(
        lambda: _micro_row_wise(args.rows, args.wide_fields, args.deps), args.runs
    )

    ew = results["engine_wide_many_call_by"]
    en = results["engine_narrow_few_call_by"]
    mf = results["micro_field_major"]
    mr = results["micro_row_wise"]

    comparisons = {
        "engine_wide_over_narrow_duration": (
            ew["duration_s_median"] / en["duration_s_median"] if en["duration_s_median"] else None
        ),
        "engine_wide_calc_calls": ew.get("calc_calls"),
        "engine_narrow_calc_calls": en.get("calc_calls"),
        "micro_dep_reads_field_major": mf.get("dep_reads"),
        "micro_dep_reads_row_wise": mr.get("dep_reads"),
        "micro_dep_reads_ratio_field_over_row": (
            float(mf["dep_reads"]) / float(mr["dep_reads"]) if mr.get("dep_reads") else None
        ),
        "micro_duration_speedup_row_over_field": (
            mf["duration_s_median"] / mr["duration_s_median"] if mr["duration_s_median"] else None
        ),
        "note": (
            "Engine cases show current Scalim cost grows with M (field count) for thin call_by. "
            "Micro loops show same-deps row-wise cuts dep_reads from ~N*M*D to ~N*D while calc_calls stay N*M."
        ),
    }

    report = {
        "topic": "c20-nxm-framework-tax",
        "change": "c20-compute-expr-rowwise-fusion",
        "python": "{}.{}".format(sys.version_info[0], sys.version_info[1]),
        "params": {
            "rows": args.rows,
            "wide_fields": args.wide_fields,
            "narrow_fields": args.narrow_fields,
            "deps": args.deps,
            "runs": args.runs,
        },
        "results": results,
        "comparisons": comparisons,
        "example_walkthrough": {
            "N": 2,
            "M": 3,
            "D": 2,
            "field_major_dep_reads": 2 * 3 * 2,
            "row_wise_dep_reads": 2 * 2,
            "calc_calls_both": 2 * 3,
        },
    }

    path = os.path.join(out_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps(comparisons, ensure_ascii=False, indent=2, sort_keys=True))
    print("report ->", path)


if __name__ == "__main__":
    main()
