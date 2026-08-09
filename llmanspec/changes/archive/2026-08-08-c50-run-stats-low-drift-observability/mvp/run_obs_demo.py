# -*- coding: utf-8 -*-
"""Scalim observability sampling demo (synthetic workload).

Usage (from repo root):
  uv run python llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/run_obs_demo.py --scale smoke
  uv run python llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/run_obs_demo.py --scale mid
  uv run python llmanspec/changes/archive/2026-08-08-c50-run-stats-low-drift-observability/mvp/run_obs_demo.py --scale stress --profiles baseline,bench

Default outputs under .tmp/obs-demo/runs/<scale>_<ts>/ (JSON for viz; work/ removed after fingerprints).
Pinned slim evidence lives next to this harness under evidence/.
"""

from __future__ import print_function

import argparse
import gc
import os
import shutil
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.abspath(os.path.dirname(__file__))


def _find_repo_root(start):
    # type: (str) -> str
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "pyproject.toml")) and os.path.isdir(os.path.join(cur, "src", "scalim")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError("cannot locate scalim repo root from {}".format(start))
        cur = parent


REPO_ROOT = _find_repo_root(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from obs_demo_pkg import loaders as loaders_mod  # noqa: E402
from obs_demo_pkg.collect import (  # noqa: E402
    atomic_write_json,
    build_run_stats,
    fingerprint_path,
    rss_mb,
    wall_payload,
)
from obs_demo_pkg.profiles import apply_env, build_profile, restore_env  # noqa: E402
from obs_demo_pkg.shapes import shape_for, usable_bytes  # noqa: E402

from scalim.ob.presets.run_stats import write_run_stats_sibling  # noqa: E402
from scalim.dsl.yaml_dsl import (  # noqa: E402
    BookResourcePolicy,
    BookWriteAlignBy,
    BookWriteHeaderPolicy,
    BookWriteMode,
    BookWriteOnConflict,
    BookWriteOnMismatch,
    BookWritePolicy,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ResourcesPolicy,
    RunOverrides,
    WorkflowRunOptions,
    run_workflow,
)
from scalim.shortcuts.resources import outputs as outputs_api  # noqa: E402


DEFAULT_PROFILES_BY_SCALE = {
    "smoke": ["baseline", "bench", "bench_plus", "debug", "probe"],
    "mid": ["baseline", "bench", "bench_plus", "debug", "probe"],
    "stress": ["baseline", "bench"],
}


def _copy_workload(dst_dir):
    # type: (str) -> str
    src = os.path.join(HERE, "workload")
    dst = os.path.join(dst_dir, "workload")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return os.path.join(dst, "workflow.yaml")


def _sampling_interval(shape, profile):
    # type: (Dict[str, Any], str) -> int
    rows = int(shape["fact_rows"])
    if profile in ("bench_plus", "debug"):
        if rows >= 500000:
            return 20
        if rows >= 100000:
            return 10
        return 2
    if rows >= 500000:
        return 10
    if rows >= 100000:
        return 5
    return 1


def _resolve_artifacts(out_root):
    # type: (str) -> Dict[str, Any]
    """Resolve books/files under workload-relative out/ (YAML cwd)."""
    result = {"books": {}, "files": {}, "errors": [], "roots_tried": []}  # type: Dict[str, Any]
    candidates = [
        os.path.join(out_root, "workload", "out", "report"),
        os.path.join(out_root, "out", "report"),
    ]
    for report_root in candidates:
        result["roots_tried"].append(report_root)
        if not os.path.isdir(report_root):
            continue
        try:
            latest = outputs_api.load_latest_outputs(report_root)
            for book_id, path in (latest.books or {}).items():
                result["books"][str(book_id)] = fingerprint_path(str(path))
            result["run_id"] = latest.run_id
            break
        except Exception as exc:  # noqa: BLE001
            result["errors"].append({"where": "report_book", "root": report_root, "type": type(exc).__name__, "msg": str(exc)})

    for label, rels in (
        ("detail_csv", ("workload/out/detail_csv", "out/detail_csv")),
        ("metrics_csv", ("workload/out/metrics_csv", "out/metrics_csv")),
    ):
        found = False
        for rel in rels:
            root = os.path.join(out_root, *rel.split("/"))
            result["roots_tried"].append(root)
            if not os.path.isdir(root):
                continue
            try:
                latest = outputs_api.load_latest_outputs(root)
                for fid, path in (latest.files or {}).items():
                    result["files"]["{}.{}".format(label, fid)] = fingerprint_path(str(path))
                found = True
                break
            except Exception as exc:  # noqa: BLE001
                csv_files = []
                for dirpath, _dirs, files in os.walk(root):
                    for name in files:
                        if name.endswith(".csv"):
                            csv_files.append(os.path.join(dirpath, name))
                if csv_files:
                    csv_files.sort()
                    result["files"][label] = fingerprint_path(csv_files[-1])
                    found = True
                    break
                result["errors"].append({"where": label, "root": root, "type": type(exc).__name__, "msg": str(exc)})
        if not found and label not in result["files"]:
            result["errors"].append({"where": label, "msg": "not found"})
    return result


def _run_one(scale, shape, profile_name, run_root):
    # type: (str, Dict[str, Any], str, str) -> Dict[str, Any]
    profile_dir = os.path.join(run_root, "runs", profile_name)
    os.makedirs(profile_dir, exist_ok=True)
    work_dir = os.path.join(profile_dir, "work")
    if os.path.isdir(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir)

    wf_path = _copy_workload(work_dir)
    interval = _sampling_interval(shape, profile_name)
    built = build_profile(profile_name, run_dir=profile_dir, sampling_interval=interval)

    loaders_mod.configure_shape(shape["fact_rows"], shape["dim_rows"], shape["region_rows"])

    allowed_modules = frozenset(
        [
            "obs_demo_pkg.loaders",
            "scalim.workflow.loaders",
        ]
    )
    demand_options = DemandRunOptions(
        security=DemandRunSecurityOptions(
            allowed_modules=allowed_modules,
            allowed_yaml_roots=(REPO_ROOT, HERE, work_dir),
        ),
        template=DemandRunTemplateOptions(init_vars={"fact_ids": []}),
        runtime=DemandRunRuntimeOptions(
            components=list(built["components"]),
            batch_size=int(shape["batch_size"]),
            parallel_mode=str(shape.get("parallel_mode") or "seq"),
        ),
        outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=built["viz_config"]) if built.get("viz_config") else None),
    )
    resources_policy = ResourcesPolicy(
        books={
            "report": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.SHEET,
                    on_conflict=BookWriteOnConflict.OVERWRITE,
                    align_by=BookWriteAlignBy.FIELD_ID,
                    header_policy=BookWriteHeaderPolicy.ONCE,
                    on_mismatch=BookWriteOnMismatch.ERROR,
                )
            ),
            "scratch": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.SHEET,
                    on_conflict=BookWriteOnConflict.OVERWRITE,
                )
            ),
        }
    )

    prev_env = apply_env(built.get("env") or {})
    rss_before = rss_mb()
    t0 = time.perf_counter()
    exit_code = 0
    err = None  # type: Optional[Dict[str, Any]]
    wf_result = None
    try:
        wf_result = run_workflow(
            wf_path,
            options=WorkflowRunOptions(
                demand=demand_options,
                path_aliases={"@": REPO_ROOT},
                resources_policy=resources_policy,
            ),
        )
        errors = list(wf_result.errors() or [])
        if errors:
            exit_code = 1
            err = {"workflow_errors": [str(e) for e in errors[:20]]}
    except Exception as exc:  # noqa: BLE001
        exit_code = 2
        err = {"exc_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        restore_env(prev_env)

    elapsed = time.perf_counter() - t0
    rss_after = rss_mb()

    handles = built["handles"]
    run_stats = build_run_stats(
        handles.get("accum"),
        perf_observer=handles.get("perf"),
        meta={
            "scale": scale,
            "profile": profile_name,
            "shape": shape,
            "profile_meta": built.get("meta"),
        },
    )
    atomic_write_json(os.path.join(profile_dir, "run_stats.json"), run_stats)
    try:
        write_run_stats_sibling(profile_dir, run_stats)
    except Exception:  # noqa: BLE001
        pass
    artifacts = _resolve_artifacts(work_dir)
    # Drop bulky workbook/csv trees; keep JSON next to profile for viz ingest.
    if os.path.isdir(work_dir):
        shutil.rmtree(work_dir)
    viz_dir = os.path.join(profile_dir, "viz")
    if os.path.isdir(viz_dir):
        shutil.rmtree(viz_dir)

    # Stage memory samples (if any)
    stage_memory = None
    sm = handles.get("stage_memory")
    if sm is not None and getattr(sm, "samples", None) is not None:
        stage_memory = [
            {
                "batch_num": s.batch_num,
                "stage": s.stage,
                "duration_s": s.duration_s,
                "rss_mb": s.rss_mb,
                "delta_mb": s.delta_mb,
            }
            for s in sm.samples
        ]

    relation = None
    rel = handles.get("relation")
    if rel is not None and hasattr(rel, "metrics"):
        m = rel.metrics
        relation = {
            "total_lookups": getattr(m, "total_lookups", None),
            "hit_count": getattr(m, "hit_count", None),
            "miss_count": getattr(m, "miss_count", None),
            "null_key_count": getattr(m, "null_key_count", None),
            "type_error_count": getattr(m, "type_error_count", None),
        }

    wall = wall_payload(
        profile_name,
        elapsed,
        exit_code=exit_code,
        extras={
            "rss_mb_before": rss_before,
            "rss_mb_after": rss_after,
            "rss_delta_mb": (None if rss_before is None or rss_after is None else round(rss_after - rss_before, 2)),
            "error": err,
        },
    )

    meta = {
        "scale": scale,
        "profile": profile_name,
        "shape": shape,
        "events_expected": built.get("events_expected"),
        "collectors": (built.get("meta") or {}).get("collectors") or [],
        "usable_bytes": usable_bytes(),
    }
    atomic_write_json(os.path.join(profile_dir, "meta.json"), meta)
    atomic_write_json(os.path.join(profile_dir, "wall.json"), wall)
    atomic_write_json(os.path.join(profile_dir, "run_stats.json"), run_stats)
    atomic_write_json(os.path.join(profile_dir, "artifacts.json"), artifacts)
    if stage_memory is not None:
        atomic_write_json(os.path.join(profile_dir, "stage_memory.json"), {"samples": stage_memory})
    if relation is not None:
        atomic_write_json(os.path.join(profile_dir, "relation.json"), relation)
    if handles.get("perf") is not None:
        atomic_write_json(os.path.join(profile_dir, "perf_last_pipeline.json"), handles["perf"].get_metrics().to_dict())

    covered = []  # type: List[str]
    pipe = run_stats.get("pipeline") or {}
    if pipe.get("total_duration_s"):
        covered.append("pipeline.total_duration_s")
    if pipe.get("total_rows_in"):
        covered.append("pipeline.total_rows_in")
    if pipe.get("node_count"):
        covered.append("pipeline.node_count")
    if any(float(v or 0) > 0 for v in (run_stats.get("stages_total") or {}).values()):
        covered.append("stages_total")
    if run_stats.get("loaders"):
        covered.append("loaders")
    if run_stats.get("batches"):
        covered.append("batches[]")
    if run_stats.get("outputs"):
        covered.append("outputs[]")
    if run_stats.get("nodes"):
        covered.append("nodes[]")
    if (run_stats.get("memory") or {}).get("peak_mb") is not None:
        covered.append("memory.peak_mb")
    if stage_memory:
        covered.append("stage_memory.samples")
    if relation and int(relation.get("total_lookups") or 0) > 0:
        covered.append("relation.lookups")
    if os.path.isdir(os.path.join(profile_dir, "viz")):
        covered.append("viz")
    if artifacts.get("books") or artifacts.get("files"):
        covered.append("artifacts")

    return {
        "profile": profile_name,
        "wall": wall,
        "covered_fields": covered,
        "artifacts": artifacts,
        "exit_code": exit_code,
        "run_stats_schema": run_stats.get("schema"),
        "profile_dir": profile_dir,
    }


def _compare_outputs(baseline_art, other_art):
    # type: (Dict[str, Any], Dict[str, Any]) -> Dict[str, Any]
    """Compare CSV fingerprints primarily (xlsx often non-deterministic metadata)."""
    mismatches = []  # type: List[Dict[str, Any]]
    notes = []  # type: List[str]
    b_files = baseline_art.get("files") or {}
    o_files = other_art.get("files") or {}
    keys = sorted(set(b_files) | set(o_files))
    if not keys:
        notes.append("no csv fingerprints; falling back to book size-only check")
        b_books = baseline_art.get("books") or {}
        o_books = other_art.get("books") or {}
        for key in sorted(set(b_books) | set(o_books)):
            b = b_books.get(key) or {}
            o = o_books.get(key) or {}
            if b.get("size") != o.get("size"):
                mismatches.append({"kind": "book_size", "id": key, "baseline": b.get("size"), "other": o.get("size")})
    for key in keys:
        b = b_files.get(key) or {}
        o = o_files.get(key) or {}
        if b.get("size") != o.get("size") or b.get("sha256_head") != o.get("sha256_head"):
            mismatches.append({"kind": "file", "id": key, "baseline": b, "other": o})
    # Book presence check (not byte-identical): both sides must have same book ids when present.
    b_book_ids = set((baseline_art.get("books") or {}).keys())
    o_book_ids = set((other_art.get("books") or {}).keys())
    if b_book_ids != o_book_ids:
        mismatches.append({"kind": "book_ids", "baseline": sorted(b_book_ids), "other": sorted(o_book_ids)})
    return {"ok": len(mismatches) == 0, "mismatches": mismatches, "notes": notes}


def build_sampling_matrix(scale, shape, results):
    # type: (str, Dict[str, Any], List[Dict[str, Any]]) -> Dict[str, Any]
    baseline = None
    for r in results:
        if r["profile"] == "baseline":
            baseline = r
            break
    rows = []
    for r in results:
        wall = r["wall"]
        cmp = None
        if baseline is not None and r["profile"] != "baseline":
            cmp = _compare_outputs(baseline.get("artifacts") or {}, r.get("artifacts") or {})
        base_elapsed = (baseline or {}).get("wall", {}).get("elapsed_s")
        obs_tax = None
        if base_elapsed and wall.get("elapsed_s"):
            obs_tax = round((float(wall["elapsed_s"]) / float(base_elapsed) - 1.0) * 100.0, 2)
        rows.append(
            {
                "profile": r["profile"],
                "elapsed_s": wall.get("elapsed_s"),
                "rss_delta_mb": wall.get("rss_delta_mb"),
                "rss_mb_after": wall.get("rss_mb_after"),
                "exit_code": r.get("exit_code"),
                "covered_fields": r.get("covered_fields"),
                "obs_tax_pct_vs_baseline": obs_tax,
                "output_equiv_vs_baseline": None if cmp is None else cmp.get("ok"),
                "output_mismatches": None if cmp is None else len(cmp.get("mismatches") or []),
            }
        )
    return {
        "schema": "scalim_obs_demo_sampling_matrix/v0",
        "scale": scale,
        "shape": shape,
        "usable_bytes": usable_bytes(),
        "usable_gb": round(usable_bytes() / (1024.0**3), 2),
        "profiles": rows,
        "notes": [
            "Observers must not change sink bytes (output_equiv_vs_baseline).",
            "Memory profiles require psutil (no silent fallback).",
            "JSON artifacts are intended for later viz ingestion.",
        ],
    }


def main(argv=None):
    # type: (Optional[Sequence[str]]) -> int
    ap = argparse.ArgumentParser(description="Scalim obs-demo sampling harness")
    ap.add_argument("--scale", choices=["smoke", "mid", "stress"], default="smoke")
    ap.add_argument("--profiles", default=None, help="comma list; default depends on scale")
    ap.add_argument(
        "--out-root",
        default=None,
        help="default: <repo>/.tmp/obs-demo/runs/<scale>_<ts>",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)

    shape = shape_for(args.scale)
    profiles = (
        [p.strip() for p in str(args.profiles).split(",") if p.strip()] if args.profiles else list(DEFAULT_PROFILES_BY_SCALE[args.scale])
    )

    ts = time.strftime("%Y%m%d_%H%M%S")
    run_root = args.out_root or os.path.join(REPO_ROOT, ".tmp", "obs-demo", "runs", "{}_{}".format(args.scale, ts))
    os.makedirs(run_root, exist_ok=True)
    atomic_write_json(os.path.join(run_root, "shape.json"), shape)

    print("obs-demo scale={} profiles={} out={}".format(args.scale, profiles, run_root))
    print("shape={}".format(shape))
    print("mem_soft_cap_gb={}".format(shape.get("mem_soft_cap_gb")))

    # Warmup (discarded): remove cold-import bias from first timed profile.
    print("--- warmup baseline (discard) ---")
    warmup_root = os.path.join(run_root, "_warmup")
    _ = _run_one(args.scale, shape, "baseline", warmup_root)
    if os.path.isdir(warmup_root):
        shutil.rmtree(warmup_root)
    gc.collect()

    results = []  # type: List[Dict[str, Any]]
    for name in profiles:
        print("--- profile {} ---".format(name))
        gc.collect()
        r = _run_one(args.scale, shape, name, run_root)
        results.append(r)
        print(
            "  elapsed={:.3f}s exit={} rss_delta={} covered={}".format(
                float(r["wall"].get("elapsed_s") or 0),
                r.get("exit_code"),
                r["wall"].get("rss_delta_mb"),
                ",".join(r.get("covered_fields") or []),
            )
        )
        if r.get("exit_code"):
            print("  ERROR:", (r["wall"].get("error") or {}))

    matrix = build_sampling_matrix(args.scale, shape, results)
    atomic_write_json(os.path.join(run_root, "sampling_matrix.json"), matrix)
    atomic_write_json(os.path.join(run_root, "summary.json"), {"results": results, "matrix": matrix})
    print("wrote", os.path.join(run_root, "sampling_matrix.json"))
    return 0 if all(int(r.get("exit_code") or 0) == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
