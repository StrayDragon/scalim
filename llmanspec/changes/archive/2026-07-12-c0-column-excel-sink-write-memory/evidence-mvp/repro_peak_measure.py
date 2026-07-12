#!/usr/bin/env python3
"""Pinned peak measure for production ColumnExcelSink (write_only close).

Output: .tmp/evidence/column-excel-peak/<ts>/result.json
Aborts if RSS exceeds --max-rss-gb (default 28).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _rss_gb() -> float:
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as handle:
            parts = handle.read().strip().split()
        if not parts:
            return 0.0
        return int(parts[1]) * os.sysconf("SC_PAGE_SIZE") / 1024.0 / 1024.0 / 1024.0
    except Exception:
        return 0.0


class RssBudgetExceeded(RuntimeError):
    pass


def measure(*, out_path: Path, n_rows: int, n_cols: int, max_rss_gb: float) -> Dict[str, Any]:
    from scalim.sinks import ColumnExcelSink

    field_names = ["f{}".format(i) for i in range(n_cols)]
    row_ids = list(range(n_rows))
    peak = {"v": _rss_gb()}
    stop = {"v": False}

    def _sampler() -> None:
        while not stop["v"]:
            cur = _rss_gb()
            peak["v"] = max(peak["v"], cur)
            if cur >= max_rss_gb:
                stop["v"] = True
            time.sleep(0.05)

    thr = threading.Thread(target=_sampler)
    thr.daemon = True
    thr.start()
    try:
        sink = ColumnExcelSink(str(out_path), field_names=field_names, include_header=True)
        sink.set_row_ids(row_ids)
        for i, name in enumerate(field_names):
            sink.write_column(name, {r: r * 10 + i for r in row_ids})
            if peak["v"] >= max_rss_gb:
                raise RssBudgetExceeded("RSS {:.2f}GB >= {:.2f}GB during write".format(peak["v"], max_rss_gb))
        gc.collect()
        pre = _rss_gb()
        peak["v"] = max(peak["v"], pre)
        t0 = time.perf_counter()
        sink.close()
        close_s = time.perf_counter() - t0
        post = _rss_gb()
        peak["v"] = max(peak["v"], post)
        if peak["v"] >= max_rss_gb:
            raise RssBudgetExceeded("RSS {:.2f}GB >= {:.2f}GB".format(peak["v"], max_rss_gb))
        return {
            "ok": True,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "cells": n_rows * n_cols,
            "rss_gb_pre_close": pre,
            "rss_gb_post_close": post,
            "peak_rss_gb": peak["v"],
            "duration_close_s": close_s,
            "bytes_on_disk": out_path.stat().st_size if out_path.exists() else 0,
        }
    finally:
        stop["v"] = True
        thr.join(timeout=2.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--cols", type=int, default=300)
    parser.add_argument("--max-rss-gb", type=float, default=28.0)
    parser.add_argument("--out-dir", type=str, default="")
    parser.add_argument("--keep-xlsx", action="store_true")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir or os.path.join(".tmp", "evidence", "column-excel-peak", ts))
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx = out_dir / "out.xlsx"
    try:
        result = measure(out_path=xlsx, n_rows=int(args.rows), n_cols=int(args.cols), max_rss_gb=float(args.max_rss_gb))
    except RssBudgetExceeded as exc:
        result = {"ok": False, "error": str(exc), "peak_rss_gb": _rss_gb()}
    if not args.keep_xlsx and xlsx.exists():
        try:
            xlsx.unlink()
        except OSError:
            pass
    report = {
        "topic": "column-excel-peak",
        "pinned_script": str(Path(__file__).as_posix()),
        "budget_max_rss_gb": float(args.max_rss_gb),
        "result": result,
    }
    path = out_dir / "result.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print("report -> {}".format(path))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
