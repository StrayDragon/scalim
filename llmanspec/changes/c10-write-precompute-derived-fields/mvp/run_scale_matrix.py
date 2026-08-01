#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c10 scale matrix: ~5GB / ~15GB / ~30GB cross-validation baselines.

Cross product (sim always; engine optional per scale):
  scale:     small(~5GiB) | medium(~15GiB) | large(~30GiB) | smoke
  topology:  flat | chain | mixed
  sink:      row | column

Memory estimate uses calibrated ~64 bytes/derived-cell (eager full-hold model).
Engine runs use validating discard sinks so output is NOT retained (checks golden on the fly).

Usage:
  uv run python .../run_scale_matrix.py --scales smoke,small,medium,large --sim-only --write-baseline
  uv run python .../run_scale_matrix.py --scales smoke,small_engine,medium_engine,large_engine --engine --write-baseline
  uv run python .../run_scale_matrix.py --scales small --engine --allow-rss-gb 12
"""

from __future__ import absolute_import, print_function

import argparse
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple


BYTES_PER_CELL = 64.0  # calibrated ~58–74 on column eager hold
GIB = 1024.0 ** 3


def _repo_root():
    # type: () -> str
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "..", ".."))


def _ensure_src_path():
    # type: () -> None
    src = os.path.join(_repo_root(), "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _rss_bytes():
    # type: () -> int
    try:
        with open("/proc/self/statm", "r") as f:
            return int(int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE"))
    except Exception:
        return 0


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


# ---------------------------------------------------------------------------
# Scale definitions (eager full-hold derived cells → target GiB)
# ---------------------------------------------------------------------------


def _scale_params(target_gib, topology, width_mode="full"):
    # type: (float, str, str) -> Dict[str, Any]
    """Pick rows/flat/chain so rows*(flat+chain)*BYTES ≈ target_gib GiB.

    width_mode:
      - full: wide tables (many late candidates) for residency sims at 5/15/30GiB
      - engine: narrower plans so golden A/B finishes in minutes while keeping topologies
    """
    target_cells = int(target_gib * GIB / BYTES_PER_CELL)
    if width_mode == "engine":
        if topology == "flat":
            flat, chain = 120, 0
        elif topology == "chain":
            flat, chain = 8, 48
        else:
            flat, chain = 80, 16
    elif topology == "flat":
        # prefer wider tables (many late candidates)
        flat = 1600 if target_gib <= 6 else (2400 if target_gib <= 18 else 3200)
        chain = 0
    elif topology == "chain":
        chain = 64 if target_gib <= 6 else (96 if target_gib <= 18 else 128)
        flat = 8
    else:  # mixed
        chain = 16 if target_gib <= 6 else (24 if target_gib <= 18 else 32)
        flat = 800 if target_gib <= 6 else (1200 if target_gib <= 18 else 1600)

    if topology == "flat":
        rows = max(1000, target_cells // max(flat, 1))
    elif topology == "chain":
        rows = max(1000, target_cells // max(chain, 1))
    else:
        rows = max(1000, target_cells // max(flat + chain, 1))

    cells = rows * (flat + chain)
    return {
        "rows": int(rows),
        "flat_fields": int(flat),
        "chain_depth": int(chain),
        "derived_cells": int(cells),
        "est_eager_hold_gib": float(cells) * BYTES_PER_CELL / GIB,
        "topology": topology,
        "width_mode": width_mode,
    }


SCALES = {
    "smoke": {
        "target_gib": 0.02,
        "note": "fast CI / local sanity",
        "topologies": ("flat", "chain", "mixed"),
    },
    "small": {
        "target_gib": 5.0,
        "note": "~5GiB eager full-hold estimate",
        "topologies": ("flat", "chain", "mixed"),
    },
    "medium": {
        "target_gib": 15.0,
        "note": "~15GiB eager full-hold estimate",
        "topologies": ("flat", "chain", "mixed"),
    },
    "large": {
        "target_gib": 30.0,
        "note": "~30GiB eager full-hold estimate",
        "topologies": ("flat", "chain", "mixed"),
    },
    # Engine proxies: same topologies as 5/15/30 tiers; narrower plans + ~0.25–0.75GiB cells
    # Full 5/15/30GiB engine runs need --scales small|medium|large --engine --allow-rss-gb …
    "small_engine": {
        "target_gib": 0.25,
        "note": "engine proxy ↔ small(~5GiB) sims; golden+topology cross-check",
        "topologies": ("flat", "chain", "mixed"),
        "tier_alias": "small",
        "width_mode": "engine",
    },
    "medium_engine": {
        "target_gib": 0.5,
        "note": "engine proxy ↔ medium(~15GiB) sims",
        "topologies": ("flat", "chain", "mixed"),
        "tier_alias": "medium",
        "width_mode": "engine",
    },
    "large_engine": {
        "target_gib": 0.75,
        "note": "engine proxy ↔ large(~30GiB) sims",
        "topologies": ("flat", "chain", "mixed"),
        "tier_alias": "large",
        "width_mode": "engine",
    },
}


def sim_row_eager(rows, flat, chain):
    # type: (int, int, int) -> Dict[str, Any]
    n = flat + chain
    return {
        "peak_derived_cells": rows * n,
        "calc_calls": rows * n,
        "dep_reads": rows * flat * 2 + rows * chain,
    }


def sim_row_late(rows, flat, chain):
    # type: (int, int, int) -> Dict[str, Any]
    n = flat + chain
    return {
        "peak_derived_cells": n,  # one row
        "calc_calls": rows * n,
        "dep_reads": rows * (flat * 2 + chain),
    }


def sim_column_eager(rows, flat, chain):
    # type: (int, int, int) -> Dict[str, Any]
    n = flat + chain
    return {
        "peak_derived_cells": rows * n,
        "calc_calls": rows * n,
        "dep_reads": rows * flat * 2 + rows * chain,
    }


def sim_column_late(rows, flat, chain):
    # type: (int, int, int) -> Dict[str, Any]
    # retain chain prefix until dependents written; flats one-at-a-time
    peak = rows if chain <= 0 else rows * chain
    n = flat + chain
    return {
        "peak_derived_cells": peak,
        "calc_calls": rows * n,
        "dep_reads": rows * flat * 2 + rows * chain,
        "retain_model": "chain_prefix_until_dependents_written",
    }


# ---------------------------------------------------------------------------
# Validating discard sinks (engine correctness without retaining output)
# ---------------------------------------------------------------------------


def _build_demand(flat, chain):
    # type: (int, int) -> Tuple[Any, Any, Any, List[str]]
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

    for i in range(flat):
        fid = "d%d" % i

        def _mf(idx):
            # type: (int) -> Callable[..., Any]
            return lambda a, b: expected_flat(float(a or 0), float(b or 0), idx)

        fields.append(
            DerivedFieldIr(
                field_id=fid,
                name=fid,
                dependencies=("v0", "v1"),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id=fid + ".calculator"),
                    args=(
                        CallByValueIr(kind="field", value="v0"),
                        CallByValueIr(kind="field", value="v1"),
                    ),
                ),
            )
        )
        calcs[fid] = _mf(i)
        targets.append(fid)

    prev = "v0"
    for k in range(chain):
        fid = "c%d" % k
        dep = prev
        fields.append(
            DerivedFieldIr(
                field_id=fid,
                name=fid,
                dependencies=(dep,),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id=fid + ".calculator"),
                    args=(CallByValueIr(kind="field", value=dep),),
                ),
            )
        )
        calcs[fid] = lambda x: float(x or 0) + 1.0
        targets.append(fid)
        prev = fid

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=targets)
    bindings = RuntimeBindings(derived_calculators=calcs)
    return demand, plan, bindings, targets


def run_engine_case(params, sink_kind, batch_size, allow_rss_gb):
    # type: (Dict[str, Any], str, int, float) -> Dict[str, Any]
    from scalim.execution.engine import ScalimEngine
    from scalim.sinks._internal.base import BaseRowSink, ColumnBatch, ColumnValues, IColumnSink
    from scalim.typedefs import RowData
    from scalim.vendor.compact.typing_extensionsx import override

    rows = int(params["rows"])
    flat = int(params["flat_fields"])
    chain = int(params["chain_depth"])
    demand, plan, bindings, targets = _build_demand(flat, chain)
    data = [{"id": i, "v0": float(i % 97), "v1": float(i % 13)} for i in range(rows)]

    rss0 = _rss_bytes()
    limit = int(allow_rss_gb * GIB) if allow_rss_gb > 0 else 0

    class ValidatingRowSink(BaseRowSink):
        def __init__(self):
            # type: () -> None
            self._i = 0
            self.checked = 0
            self.mismatches = 0
            self._peak_rss = _rss_bytes()
            self._closed = False

        @override
        def write_row(self, row):
            # type: (RowData) -> None
            if self._i >= rows:
                return
            i = self._i
            v0 = float(i % 97)
            v1 = float(i % 13)
            expect = {"id": float(i), "v0": v0, "v1": v1}  # type: Dict[str, float]
            for f in range(flat):
                expect["d%d" % f] = expected_flat(v0, v1, f)
            for k in range(chain):
                expect["c%d" % k] = expected_chain(v0, k)
            for key, ev in expect.items():
                self.checked += 1
                gv = row.get(key)
                if float(gv if gv is not None else 0) != float(ev):
                    self.mismatches += 1
            self._i += 1
            self._peak_rss = max(self._peak_rss, _rss_bytes())

        def write_row_aligned(self, field_keys, values):
            # type: (Sequence[str], Sequence[Any]) -> None
            self.write_row(dict(zip(list(field_keys), list(values))))

        @override
        def close(self):
            # type: () -> None
            self._closed = True

        @override
        def discard(self):
            # type: () -> None
            self._closed = True

    class ValidatingColumnSink(IColumnSink):
        def __init__(self):
            # type: () -> None
            self._row_ids = []  # type: List[Any]
            self._id_by_rid = {}  # type: Dict[Any, int]
            self.checked = 0
            self.mismatches = 0
            self._peak_rss = _rss_bytes()
            self._closed = False

        @override
        def set_row_ids(self, row_ids):
            # type: (Sequence[Any]) -> None
            self._row_ids = list(row_ids)
            self._id_by_rid = {}

        @override
        def write_column(self, field_key, values):
            # type: (str, ColumnValues) -> None
            self._peak_rss = max(self._peak_rss, _rss_bytes())
            mapping = dict(values)
            if field_key == "id":
                for rid, val in mapping.items():
                    self._id_by_rid[rid] = int(float(val or 0))
            for rid in self._row_ids:
                if rid not in mapping:
                    continue
                i = self._id_by_rid.get(rid)
                if i is None:
                    continue
                v0 = float(i % 97)
                v1 = float(i % 13)
                ev = None  # type: Optional[float]
                if field_key == "id":
                    ev = float(i)
                elif field_key == "v0":
                    ev = v0
                elif field_key == "v1":
                    ev = v1
                elif field_key.startswith("d") and field_key[1:].isdigit():
                    ev = expected_flat(v0, v1, int(field_key[1:]))
                elif field_key.startswith("c") and field_key[1:].isdigit():
                    ev = expected_chain(v0, int(field_key[1:]))
                if ev is None:
                    continue
                self.checked += 1
                gv = mapping.get(rid)
                if float(gv if gv is not None else 0) != float(ev):
                    self.mismatches += 1

        @override
        def write_columns(self, columns):
            # type: (ColumnBatch) -> None
            for k, v in columns.items():
                self.write_column(k, v)

        def write_column_aligned(self, field_key, row_ids, values):
            # type: (str, Sequence[Any], Sequence[Any]) -> None
            mapping = {}
            for rid, val in zip(list(row_ids), list(values)):
                mapping[rid] = val
            self.write_column(field_key, mapping)

        @override
        def close(self):
            # type: () -> None
            self._closed = True

        @override
        def discard(self):
            # type: () -> None
            self._id_by_rid.clear()
            self._closed = True

    sink = ValidatingRowSink() if sink_kind == "row" else ValidatingColumnSink()  # type: Any

    t0 = time.perf_counter()
    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=bindings,
        parallel_mode="seq",
        batch_size=batch_size,
    )
    aborted = False
    try:
        engine.run(main_rows=data, sink=sink)
        sink.close()
    except Exception as exc:
        try:
            sink.discard()
        except Exception:
            pass
        return {
            "ok": False,
            "error": repr(exc),
            "sink": sink_kind,
            "params": params,
        }
    t1 = time.perf_counter()
    rss1 = _rss_bytes()
    peak = max(rss1, getattr(sink, "_peak_rss", rss1))
    if limit and peak > limit:
        aborted = True

    return {
        "ok": (not aborted) and sink.mismatches == 0 and sink.checked > 0,
        "aborted_rss": aborted,
        "sink": sink_kind,
        "params": params,
        "duration_s": t1 - t0,
        "rss_kb_before": int(rss0 / 1024),
        "rss_kb_after": int(rss1 / 1024),
        "rss_kb_peak_approx": int(peak / 1024),
        "cells_checked": sink.checked,
        "mismatches": sink.mismatches,
        "golden_ok": sink.mismatches == 0 and sink.checked > 0,
    }


def run_sim_case(params, sink_kind):
    # type: (Dict[str, Any], str) -> Dict[str, Any]
    rows = int(params["rows"])
    flat = int(params["flat_fields"])
    chain = int(params["chain_depth"])
    if sink_kind == "row":
        eager = sim_row_eager(rows, flat, chain)
        late = sim_row_late(rows, flat, chain)
    else:
        eager = sim_column_eager(rows, flat, chain)
        late = sim_column_late(rows, flat, chain)
    ratio = float(eager["peak_derived_cells"]) / float(late["peak_derived_cells"])
    return {
        "sink": sink_kind,
        "params": params,
        "eager": eager,
        "late": late,
        "peak_ratio_eager_over_late": ratio,
        "est_eager_gib": float(eager["peak_derived_cells"]) * BYTES_PER_CELL / GIB,
        "est_late_gib": float(late["peak_derived_cells"]) * BYTES_PER_CELL / GIB,
    }


def cross_validate(matrix_cases):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    """Cross-scale checks: ratios monotonic with scale; golden flags; topology effects."""
    issues = []  # type: List[str]
    by_key = {}  # type: Dict[str, Dict[str, Any]]
    for c in matrix_cases:
        key = "%s|%s|%s" % (c["scale"], c["topology"], c["sink"])
        by_key[key] = c

    # For same topology+sink, larger scale should have larger eager peak cells
    for topology in ("flat", "chain", "mixed"):
        for sink in ("row", "column"):
            prev = None  # type: Optional[int]
            for scale in ("smoke", "small", "medium", "large"):
                k = "%s|%s|%s" % (scale, topology, sink)
                if k not in by_key:
                    continue
                peak = int(by_key[k]["sim"]["eager"]["peak_derived_cells"])
                if prev is not None and peak < prev:
                    issues.append("eager peak decreased %s -> %s for %s/%s" % (prev, peak, topology, sink))
                prev = peak

    # Row late peak should equal flat+chain (one row), independent of rows
    for c in matrix_cases:
        if c["sink"] != "row":
            continue
        n = int(c["params"]["flat_fields"]) + int(c["params"]["chain_depth"])
        got = int(c["sim"]["late"]["peak_derived_cells"])
        if got != n:
            issues.append("row late peak %s != derived count %s (%s)" % (got, n, c["case_id"]))

    engine_fails = [c["case_id"] for c in matrix_cases if c.get("engine") and not c["engine"].get("ok")]
    return {
        "ok": len(issues) == 0 and len(engine_fails) == 0,
        "issues": issues,
        "engine_failures": engine_fails,
        "cases": len(matrix_cases),
    }


def main():
    # type: () -> None
    _ensure_src_path()
    parser = argparse.ArgumentParser(description="c10 5/15/30GiB scale matrix")
    parser.add_argument(
        "--scales",
        type=str,
        default="smoke,small",
        help="comma list: smoke,small,medium,large",
    )
    parser.add_argument("--engine", action="store_true", help="run ScalimEngine validating sinks")
    parser.add_argument("--sim-only", action="store_true", help="force no engine")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--allow-rss-gb",
        type=float,
        default=28.0,
        help="abort marking failure if approx peak RSS exceeds this (engine)",
    )
    parser.add_argument("--out-dir", type=str, default="")
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    do_engine = bool(args.engine) and not bool(args.sim_only)
    scale_names = [s.strip() for s in args.scales.split(",") if s.strip()]

    here = os.path.abspath(os.path.dirname(__file__))
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir or os.path.join(here, "evidence", "matrix-" + ts)
    os.makedirs(out_dir, exist_ok=True)

    cases = []  # type: List[Dict[str, Any]]
    for scale in scale_names:
        if scale not in SCALES:
            raise SystemExit("unknown scale %r" % scale)
        meta = SCALES[scale]
        target = float(meta["target_gib"])
        width_mode = str(meta.get("width_mode") or "full")
        for topology in meta["topologies"]:
            params = _scale_params(target, topology, width_mode=width_mode)
            params["scale"] = scale
            params["target_gib"] = target
            params["tier_alias"] = meta.get("tier_alias") or scale
            params["note"] = meta.get("note") or ""
            for sink in ("row", "column"):
                case_id = "%s_%s_%s" % (scale, topology, sink)
                print("==> sim", case_id, "rows=%s flat=%s chain=%s est_eager=%.2fGiB" % (
                    params["rows"], params["flat_fields"], params["chain_depth"], params["est_eager_hold_gib"]
                ), flush=True)
                sim = run_sim_case(params, sink)
                entry = {
                    "case_id": case_id,
                    "scale": scale,
                    "tier_alias": params["tier_alias"],
                    "topology": topology,
                    "sink": sink,
                    "params": params,
                    "sim": sim,
                }  # type: Dict[str, Any]
                if do_engine:
                    # Guardrail: skip engine for large unless allow_rss high enough vs estimate
                    est = float(params["est_eager_hold_gib"])
                    if est > args.allow_rss_gb * 1.05:
                        print("    skip engine (est_eager %.1fGiB > allow %.1fGiB)" % (est, args.allow_rss_gb), flush=True)
                        entry["engine"] = {"ok": True, "skipped": True, "reason": "est_exceeds_allow_rss_gb"}
                    else:
                        print("    engine...", flush=True)
                        entry["engine"] = run_engine_case(params, sink, args.batch_size, args.allow_rss_gb)
                        print(
                            "    engine ok=%s golden=%s peak_rss_MB=%.1f"
                            % (
                                entry["engine"].get("ok"),
                                entry["engine"].get("golden_ok"),
                                float(entry["engine"].get("rss_kb_peak_approx") or 0) / 1024.0,
                            ),
                            flush=True,
                        )
                cases.append(entry)

    xv = cross_validate(cases)
    report = {
        "topic": "c10-scale-matrix",
        "change": "c10-write-precompute-derived-fields",
        "bytes_per_cell_calibrated": BYTES_PER_CELL,
        "scales_requested": scale_names,
        "engine_enabled": do_engine,
        "allow_rss_gb": args.allow_rss_gb,
        "cases": cases,
        "cross_validation": xv,
        "regression_contract": {
            "values": "engine golden_ok must stay true for same params",
            "row_late_peak": "always flat+chain (one row)",
            "column_late_peak": "rows*max(chain,1) retain model",
            "scale_monotonic": "eager peak cells must not shrink when scale increases",
            "fast_fail": "discard; no final artifact",
        },
    }

    path = os.path.join(out_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps({"cross_validation": xv, "cases": len(cases)}, indent=2), flush=True)
    print("report ->", path, flush=True)

    if args.write_baseline:
        # stable name includes which scales
        tag = "-".join(scale_names)
        bpath = os.path.join(here, "evidence", "baseline-matrix-%s.json" % tag)
        with open(bpath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
        print("baseline ->", bpath, flush=True)

    if not xv["ok"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
