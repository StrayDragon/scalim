#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c10 complex MVP + fixed baseline (row/column, flat + chained late).

Purpose (before engine apply):
  - Fix deterministic expected outputs for regression
  - Simulate eager vs late residency for flat and late→late chains
  - Run current engine (eager only) as wall-time / value baseline

Shapes (counts only):
  flat:   v0,v1 -> d0..d{M-1} independent
  chain:  v0 -> c0 -> c1 -> ... -> c{depth-1}  (late→late)
  mixed:  flat group + one chain (same batch)

Policy: auto-late via deps; no switches; no new YAML.
"""

from __future__ import absolute_import, print_function

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


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
    return {
        "duration_s_median": dur,
        "duration_s_all": durs,
        "rss_kb_before": rss0,
        "rss_kb_after": rss1,
        "delta_rss_kb": rss1 - rss0,
        "meta": meta,
    }


# ---------------------------------------------------------------------------
# Expected values (deterministic golden)
# ---------------------------------------------------------------------------


def expected_flat_row(v0, v1, field_index):
    # type: (float, float, int) -> float
    if field_index % 3 == 0:
        return v0 + v1
    if field_index % 3 == 1:
        return v0 - v1
    return v0 * v1


def expected_chain_value(v0, depth_index):
    # type: (float, int) -> float
    """c0 = v0+1; c_k = c_{k-1}+1 → c_k = v0 + (k+1)."""
    return v0 + float(depth_index + 1)


def golden_table(rows, n_flat, chain_depth):
    # type: (int, int, int) -> List[Dict[str, float]]
    out = []  # type: List[Dict[str, float]]
    for i in range(rows):
        v0 = float(i % 97)
        v1 = float(i % 13)
        row = {"id": float(i), "v0": v0, "v1": v1}  # type: Dict[str, float]
        for f in range(n_flat):
            row["d{}".format(f)] = expected_flat_row(v0, v1, f)
        for k in range(chain_depth):
            row["c{}".format(k)] = expected_chain_value(v0, k)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Simulations (residency / dep reads) — include chains
# ---------------------------------------------------------------------------


def sim_row_eager(rows, n_flat, chain_depth):
    # type: (int, int, int) -> Dict[str, Any]
    """Hold all derived for all rows, then emit."""
    n_derived = n_flat + chain_depth
    peak = rows * n_derived
    dep_reads = rows * n_flat * 2 + rows * (1 + sum(range(chain_depth)))
    # chain: c0 reads v0 once; c_k reads c_{k-1} once → approx rows * chain_depth reads of prior
    dep_reads = rows * n_flat * 2 + rows * chain_depth  # each chain step one dep read
    return {
        "shape": "sim_row_eager",
        "rows": rows,
        "n_flat": n_flat,
        "chain_depth": chain_depth,
        "peak_derived_cells": peak,
        "dep_reads": dep_reads,
        "calc_calls": rows * n_derived,
    }


def sim_row_late(rows, n_flat, chain_depth):
    # type: (int, int, int) -> Dict[str, Any]
    """Per row: topo late subgraph into row-local (flat + chain), write, discard."""
    n_derived = n_flat + chain_depth
    peak = n_derived  # one row's derived
    # deps: flat each 2 from v0/v1; chain c0 from v0, c_k from c_{k-1} — all row-local after first
    dep_reads = rows * (n_flat * 2 + chain_depth)
    return {
        "shape": "sim_row_late",
        "rows": rows,
        "n_flat": n_flat,
        "chain_depth": chain_depth,
        "peak_derived_cells": peak,
        "dep_reads": dep_reads,
        "calc_calls": rows * n_derived,
    }


def sim_column_eager(rows, n_flat, chain_depth):
    # type: (int, int, int) -> Dict[str, Any]
    """Hold all derived columns then write."""
    n_derived = n_flat + chain_depth
    return {
        "shape": "sim_column_eager",
        "rows": rows,
        "n_flat": n_flat,
        "chain_depth": chain_depth,
        "peak_derived_cells": rows * n_derived,
        "dep_reads": rows * n_flat * 2 + rows * chain_depth,
        "calc_calls": rows * n_derived,
        "max_retained_intermediates": n_derived,
    }


def sim_column_late_with_chain(rows, n_flat, chain_depth):
    # type: (int, int, int) -> Dict[str, Any]
    """Topo write columns: retain chain intermediates until dependents written.

    Peak model (conservative): while writing chain, retain prefix of chain columns
    still needed → worst peak ≈ rows * chain_depth at end of chain before deletes,
    plus at most 1 flat column in flight. Flat columns: peak += rows (one at a time).
    Combined worst-case peak_derived_cells ≈ rows * chain_depth (chain prefix) 
    when chain_depth >= 1, else rows.
    """
    n_derived = n_flat + chain_depth
    if chain_depth <= 0:
        peak = rows
    else:
        # After computing c0..c_{k}, retain all for dependents; peak at full chain before trim
        peak = rows * chain_depth
    # flat written one-by-one without retaining → does not raise above chain peak if chain_depth>=1
    if chain_depth == 0:
        peak = rows
    return {
        "shape": "sim_column_late_chain",
        "rows": rows,
        "n_flat": n_flat,
        "chain_depth": chain_depth,
        "peak_derived_cells": peak,
        "dep_reads": rows * n_flat * 2 + rows * chain_depth,
        "calc_calls": rows * n_derived,
        "note": "Column late+chain must retain intermediate late columns until dependents written; peak ~ rows*chain_depth before trim.",
    }


# ---------------------------------------------------------------------------
# Engine eager baselines (current behavior) — value check vs golden
# ---------------------------------------------------------------------------


def _engine_case(rows, n_flat, chain_depth, sink_kind):
    # type: (int, int, int, str) -> Callable[[], Dict[str, Any]]
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    fields = [
        FieldIr(field_id="id", name="id", source=main, is_primary=True),
        FieldIr(field_id="v0", name="v0", source=main),
        FieldIr(field_id="v1", name="v1", source=main),
    ]  # type: List[Any]
    calcs = {}  # type: Dict[str, Callable[..., Any]]
    targets = ["id", "v0", "v1"]  # type: List[str]

    for i in range(n_flat):
        fid = "d{}".format(i)

        def _make_flat(idx):
            # type: (int) -> Callable[..., Any]
            def _calc(a, b):
                # type: (Any, Any) -> Any
                return expected_flat_row(float(a or 0), float(b or 0), idx)

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

        def _make_chain(depth_idx):
            # type: (int) -> Callable[..., Any]
            def _calc(x):
                # type: (Any) -> Any
                # c_k = prev + 1; with prev=c_{k-1} or v0 → equals expected_chain_value
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
    bindings = RuntimeBindings(derived_calculators=calcs)
    data = [{"id": i, "v0": float(i % 97), "v1": float(i % 13)} for i in range(rows)]
    golden = golden_table(rows, n_flat, chain_depth)

    def _run():
        # type: () -> Dict[str, Any]
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=bindings,
            parallel_mode="seq",
            batch_size=min(200, max(1, rows)),
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
            "shape": "engine_eager_{}".format(sink_kind),
            "value_cells_checked": checked,
            "value_mismatches": mismatches,
            "golden_ok": mismatches == 0 and checked > 0,
            "got_row_count": len(got_rows),
        }

    return _run


def main():
    # type: () -> None
    _ensure_src_path()
    parser = argparse.ArgumentParser(description="c10 complex baseline MVP")
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--flat-fields", type=int, default=12)
    parser.add_argument("--chain-depth", type=int, default=5)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out-dir", type=str, default="")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Also write evidence/baseline-complex.json (stable name for regression)",
    )
    args = parser.parse_args()

    here = os.path.abspath(os.path.dirname(__file__))
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir or os.path.join(here, "evidence", "complex-" + ts)
    os.makedirs(out_dir, exist_ok=True)

    params = {
        "rows": args.rows,
        "flat_fields": args.flat_fields,
        "chain_depth": args.chain_depth,
        "runs": args.runs,
    }

    # golden fingerprint (first 3 rows keys sample)
    golden = golden_table(min(3, args.rows), args.flat_fields, args.chain_depth)

    results = {}  # type: Dict[str, Any]
    results["sim_row_eager"] = sim_row_eager(args.rows, args.flat_fields, args.chain_depth)
    results["sim_row_late"] = sim_row_late(args.rows, args.flat_fields, args.chain_depth)
    results["sim_column_eager"] = sim_column_eager(args.rows, args.flat_fields, args.chain_depth)
    results["sim_column_late_chain"] = sim_column_late_with_chain(args.rows, args.flat_fields, args.chain_depth)

    print("==> engine_eager_row", flush=True)
    results["engine_eager_row"] = _run_timed(
        _engine_case(args.rows, args.flat_fields, args.chain_depth, "row"), args.runs
    )
    print("==> engine_eager_column", flush=True)
    results["engine_eager_column"] = _run_timed(
        _engine_case(args.rows, args.flat_fields, args.chain_depth, "column"), args.runs
    )

    sr = results["sim_row_eager"]
    sl = results["sim_row_late"]
    sc = results["sim_column_eager"]
    scl = results["sim_column_late_chain"]

    comparisons = {
        "row_peak_ratio_eager_over_late": float(sr["peak_derived_cells"]) / float(sl["peak_derived_cells"]),
        "column_peak_ratio_eager_over_late_chain": float(sc["peak_derived_cells"]) / float(scl["peak_derived_cells"]),
        "engine_row_golden_ok": results["engine_eager_row"]["meta"].get("golden_ok"),
        "engine_column_golden_ok": results["engine_eager_column"]["meta"].get("golden_ok"),
        "engine_row_mismatches": results["engine_eager_row"]["meta"].get("value_mismatches"),
        "engine_column_mismatches": results["engine_eager_column"]["meta"].get("value_mismatches"),
        "regression_contract": {
            "values": "After late impl, engine output MUST match golden_table for same params",
            "peak_row": "sim_row_late.peak_derived_cells is upper-bound target for derived scratch per row",
            "peak_column_chain": "sim_column_late_chain.peak_derived_cells documents retain-until-dependents-written",
            "fast_fail": "failure MUST discard; no final artifact",
        },
    }

    report = {
        "topic": "c10-complex-baseline",
        "change": "c10-write-precompute-derived-fields",
        "decision_q3": "C-full-row-and-column-chains",
        "python": "{}.{}".format(sys.version_info[0], sys.version_info[1]),
        "params": params,
        "golden_sample_first_rows": golden,
        "results": results,
        "comparisons": comparisons,
    }

    path = os.path.join(out_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps(comparisons, ensure_ascii=False, indent=2, sort_keys=True))
    print("report ->", path)

    if args.write_baseline:
        baseline_path = os.path.join(here, "evidence", "baseline-complex.json")
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
        print("baseline ->", baseline_path)


if __name__ == "__main__":
    main()
