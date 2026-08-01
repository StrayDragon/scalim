#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c10 MVP: column-path eager vs late-at-write_column (simulation + engine baseline).

Engine does not implement late yet. This script:
  - runs current ScalimEngine + InMemoryColumnSink (eager)
  - simulates peak derived "scratch cells" for eager-hold vs late-at-write_column

No user switches / no new DSL — documents the auto-late strategy shape only.
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
    return {
        "duration_s_median": dur,
        "duration_s_all": durs,
        "rss_kb_before": rss0,
        "rss_kb_after": rss1,
        "delta_rss_kb": rss1 - rss0,
        "rows": rows,
        "rows_per_s": (float(rows) / dur) if dur > 0 and rows else None,
        "meta": meta,
    }


def _build_engine_column(rows, n_derived, late=True):
    # type: (int, int, bool) -> Callable[[], Dict[str, Any]]
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink
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

    def _make(i):
        # type: (int) -> Callable[..., Any]
        def _calc(a, b):
            # type: (Any, Any) -> Any
            calc_calls["n"] += 1
            aa = a or 0
            bb = b or 0
            if i % 3 == 0:
                return aa + bb
            if i % 3 == 1:
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
        calcs[fid] = _make(i)
        targets.append(fid)

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=targets)
    late_fields = tuple(plan.late_fields)
    if not late:
        # A/B 对照: 强制关闭 write-precompute(其余完全一致).
        plan.late_fields = ()
    bindings = RuntimeBindings(derived_calculators=calcs)
    data = [{"id": i, "v0": float(i % 97), "v1": float(i % 13)} for i in range(rows)]

    def _run():
        # type: () -> Dict[str, Any]
        calc_calls["n"] = 0
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=bindings,
            parallel_mode="seq",
            batch_size=200,
        )
        with InMemoryColumnSink(field_names=targets) as sink:
            engine.run(main_rows=data, sink=sink)
        return {
            "rows": rows,
            "fields_derived": n_derived,
            "calc_calls": calc_calls["n"],
            "expected_calc_calls": rows * n_derived,
            "sink": "InMemoryColumnSink",
            "shape": "engine_late_column" if late else "engine_eager_column",
            "late_fields": len(late_fields) if late else 0,
        }

    return _run


def _sim_eager_hold(rows, n_derived, deps):
    # type: (int, int, int) -> Dict[str, Any]
    """All derived columns exist on scratch at once, then written column-by-column."""
    v = [[float((r + d) % 97) for d in range(deps)] for r in range(rows)]
    derived = []  # type: List[List[float]]
    peak_derived_cells = 0
    dep_reads = 0
    calc_calls = 0
    for f in range(n_derived):
        col = []
        for r in range(rows):
            acc = 0.0
            for d in range(deps):
                dep_reads += 1
                acc += v[r][d]
            calc_calls += 1
            col.append(acc + float(f))
        derived.append(col)
        peak_derived_cells = max(peak_derived_cells, sum(len(c) for c in derived))
    # write columns (discard after write) — peak already hit while holding all
    written = 0
    while derived:
        derived.pop(0)
        written += 1
    return {
        "rows": rows,
        "fields_derived": n_derived,
        "peak_derived_cells": peak_derived_cells,
        "dep_reads": dep_reads,
        "calc_calls": calc_calls,
        "columns_written": written,
        "shape": "sim_eager_hold_derived",
    }


def _sim_late_at_write(rows, n_derived, deps):
    # type: (int, int, int) -> Dict[str, Any]
    """Compute one derived column only when writing it; never hold >1 derived column."""
    v = [[float((r + d) % 97) for d in range(deps)] for r in range(rows)]
    peak_derived_cells = 0
    dep_reads = 0
    calc_calls = 0
    for f in range(n_derived):
        col = []
        for r in range(rows):
            acc = 0.0
            for d in range(deps):
                dep_reads += 1
                acc += v[r][d]
            calc_calls += 1
            col.append(acc + float(f))
        peak_derived_cells = max(peak_derived_cells, len(col))
        # write + discard
        del col
    return {
        "rows": rows,
        "fields_derived": n_derived,
        "peak_derived_cells": peak_derived_cells,
        "dep_reads": dep_reads,
        "calc_calls": calc_calls,
        "columns_written": n_derived,
        "shape": "sim_late_at_write_column",
    }


def main():
    # type: () -> None
    _ensure_src_path()
    parser = argparse.ArgumentParser(description="c10 column late-vs-eager MVP")
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--derived-fields", type=int, default=40)
    parser.add_argument("--deps", type=int, default=2)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out-dir", type=str, default="")
    args = parser.parse_args()

    here = os.path.abspath(os.path.dirname(__file__))
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir or os.path.join(here, "evidence", ts)
    os.makedirs(out_dir, exist_ok=True)

    results = {}  # type: Dict[str, Any]

    print("==> engine_eager_column", flush=True)
    results["engine_eager_column"] = _run_timed(_build_engine_column(args.rows, args.derived_fields, late=False), args.runs)

    print("==> engine_late_column", flush=True)
    results["engine_late_column"] = _run_timed(_build_engine_column(args.rows, args.derived_fields, late=True), args.runs)

    print("==> sim_eager_hold_derived", flush=True)
    results["sim_eager_hold_derived"] = _run_timed(
        lambda: _sim_eager_hold(args.rows, args.derived_fields, args.deps), args.runs
    )
    print("==> sim_late_at_write_column", flush=True)
    results["sim_late_at_write_column"] = _run_timed(
        lambda: _sim_late_at_write(args.rows, args.derived_fields, args.deps), args.runs
    )

    eager = results["sim_eager_hold_derived"]["meta"]
    late = results["sim_late_at_write_column"]["meta"]
    engine_eager_s = results["engine_eager_column"]["duration_s_median"]
    engine_late_s = results["engine_late_column"]["duration_s_median"]
    comparisons = {
        "engine_duration_s_eager": engine_eager_s,
        "engine_duration_s_late": engine_late_s,
        "engine_speedup_eager_over_late": (float(engine_eager_s) / float(engine_late_s)) if engine_late_s else None,
        "engine_late_fields": results["engine_late_column"]["meta"].get("late_fields"),
        "engine_calc_calls_equal": (
            results["engine_eager_column"]["meta"].get("calc_calls") == results["engine_late_column"]["meta"].get("calc_calls")
        ),
        "peak_derived_cells_eager": eager.get("peak_derived_cells"),
        "peak_derived_cells_late": late.get("peak_derived_cells"),
        "peak_cells_ratio_eager_over_late": (
            float(eager["peak_derived_cells"]) / float(late["peak_derived_cells"])
            if late.get("peak_derived_cells")
            else None
        ),
        "dep_reads_both_sims": eager.get("dep_reads"),
        "note": (
            "Late-at-write_column keeps peak derived scratch ~1 column (N cells); "
            "eager-hold peaks at N*M. Dep reads equal in these sims (both field-major per column); "
            "CPU win is not the point here — residency shape is. Engine case is eager baseline only."
        ),
        "policy": "auto-late via existing deps only; no master switch; no new YAML",
    }

    report = {
        "topic": "c10-column-late-vs-eager",
        "change": "c10-write-precompute-derived-fields",
        "python": "{}.{}".format(sys.version_info[0], sys.version_info[1]),
        "params": {
            "rows": args.rows,
            "derived_fields": args.derived_fields,
            "deps": args.deps,
            "runs": args.runs,
        },
        "results": results,
        "comparisons": comparisons,
    }
    path = os.path.join(out_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps(comparisons, ensure_ascii=False, indent=2, sort_keys=True))
    print("report ->", path)


if __name__ == "__main__":
    main()
