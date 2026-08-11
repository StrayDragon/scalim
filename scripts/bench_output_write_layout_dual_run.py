#!/usr/bin/env python3
"""离线 `HOLD` vs `WINDOW` 双跑,用于写出布局建议阈值校准 (`c40`).

不改变默认 `run_ir` 行为.证据写入 `.tmp/evidence/c40-write-layout-dual-run/`(不入库).

用法:
  `uv run python scripts/bench_output_write_layout_dual_run.py`
  `uv run python scripts/bench_output_write_layout_dual_run.py --preset medium`
  `uv run python scripts/bench_output_write_layout_dual_run.py --rows 20000 --cols 50 --n 3`

上限:若估算 `HOLD` 峰值可能超过 `--max-rss-gb`(默认 10)则跳过该形状.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / ".tmp/evidence/c40-write-layout-dual-run"

CHILD = textwrap.dedent(
    """
import json, resource, sys, time
from scalim.execution import (
    ExecutionRequest,
    ExportLayout,
    OutputSpec,
    OutputWriteLayout,
    run_ir,
)
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

layout_s, path, rows, cols, batch = sys.argv[1:6]
rows = int(rows); cols = int(cols); batch = int(batch)
layout = OutputWriteLayout(layout_s)
main = MainSourceIr(source_id="m", loader_ref=RuntimeHandleIdIr(handle_id="m.loader"))
fields = [FieldIr(field_id="id", name="ID", source=main)] + [
    FieldIr(field_id="c%d" % i, name="C%d" % i, source=main) for i in range(cols)
]
demand_ir = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
keys = ["id"] + ["c%d" % i for i in range(cols)]

def _rows():
    for r in range(rows):
        yield {k: (r if k == "id" else "%s-%d" % (k, r % 997)) for k in keys}

req = ExecutionRequest(
    export_layout=ExportLayout(field_ids=tuple(keys), header_names=("ID",) + tuple("C%d" % i for i in range(cols))),
    output=OutputSpec(format="excel", path=path, streaming=False, include_header=True),
    runtime_bindings=RuntimeBindings(main_source_loaders={"m": _rows}),
    batch_size=batch,
    output_write_layout=layout,
)
t0 = time.perf_counter()
result = run_ir(demand_ir, req)
print(json.dumps({
    "wall_s": time.perf_counter() - t0,
    "rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
    "rows_out": result.total_rows,
    "layout": layout.value,
}))
"""
)

PRESETS: Dict[str, List[Tuple[str, int, int, int]]] = {
    # 名称, 行数, 列数, 批大小
    "small": [
        ("s_5k_30", 5000, 30, 500),
        ("s_10k_50", 10000, 50, 500),
    ],
    "medium": [
        ("m_20k_50", 20000, 50, 500),
        ("m_50k_50", 50000, 50, 1000),
        ("m_20k_100", 20000, 100, 500),
    ],
}


def _run_one(layout: str, path: Path, rows: int, cols: int, batch: int) -> Dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", CHILD, layout, str(path), str(rows), str(cols), str(batch)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _estimate_hold_rss_gb(rows: int, cols: int) -> float:
    # 来自 `c30` 参数探针:短字符串约 `130` 字节/格
    cells = rows * (cols + 1)
    return (cells * 130.0) / (1024.0**3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="small")
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--cols", type=int, default=None)
    parser.add_argument("--batch", type=int, default=1000)
    parser.add_argument("--n", type=int, default=3, help="每种 `layout` 重复次数(取中位数)")
    parser.add_argument("--max-rss-gb", type=float, default=10.0)
    parser.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    if args.rows is not None and args.cols is not None:
        shapes = [("custom", args.rows, args.cols, args.batch)]
    else:
        shapes = list(PRESETS[args.preset])

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []

    for name, rows, cols, batch in shapes:
        est = _estimate_hold_rss_gb(rows, cols)
        if est > args.max_rss_gb:
            print("跳过 {} 估算_hold_rss≈{:.2f}GB > 上限".format(name, est), flush=True)
            results.append({"name": name, "skipped": True, "est_hold_rss_gb": est})
            continue

        print("形状 {} 行={} 列={} 批={} n={}".format(name, rows, cols, batch, args.n), flush=True)
        hold_walls: List[float] = []
        hold_rss: List[int] = []
        win_walls: List[float] = []
        win_rss: List[int] = []
        rows_hold = rows_win = None
        for i in range(args.n):
            for layout, walls, rss_list in (
                ("column_hold", hold_walls, hold_rss),
                ("column_window", win_walls, win_rss),
            ):
                path = out_dir / name / layout / ("r%d.xlsx" % i)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    path.unlink()
                data = _run_one(layout, path, rows, cols, batch)
                walls.append(float(data["wall_s"]))
                rss_list.append(int(data["rss_kb"]))
                if layout == "column_hold":
                    rows_hold = data["rows_out"]
                else:
                    rows_win = data["rows_out"]
                print(
                    "  {}#{} 墙钟={:.3f}s rss_kb={}".format(layout, i, data["wall_s"], data["rss_kb"]),
                    flush=True,
                )

        assert rows_hold == rows_win == rows
        med_hw, med_ww = statistics.median(hold_walls), statistics.median(win_walls)
        med_hr, med_wr = statistics.median(hold_rss), statistics.median(win_rss)
        row = {
            "name": name,
            "rows": rows,
            "cols": cols,
            "batch": batch,
            "n": args.n,
            "hold_median_wall_s": med_hw,
            "window_median_wall_s": med_ww,
            "hold_median_rss_kb": med_hr,
            "window_median_rss_kb": med_wr,
            "rss_ratio_hold_over_window": (med_hr / med_wr) if med_wr else None,
            "wall_ratio_window_over_hold": (med_ww / med_hw) if med_hw else None,
            "rows_equal": True,
            "suggest_column_window": bool(med_hr > med_wr * 1.5),
        }
        results.append(row)
        print(
            "  → rss比 H/W={:.2f} 墙钟比 W/H={:.2f} 建议_window={}".format(
                row["rss_ratio_hold_over_window"],
                row["wall_ratio_window_over_hold"],
                row["suggest_column_window"],
            ),
            flush=True,
        )

    payload = {
        "phase": "c40_dual_run_hold_vs_window",
        "max_rss_gb": args.max_rss_gb,
        "preset": args.preset,
        "results": results,
        "note": "calibrate L1 wide_excel_peak_risk thresholds; do not wire into default run_ir",
    }
    out_path = out_dir / "dual_run.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("已写入", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
