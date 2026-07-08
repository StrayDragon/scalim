"""Scalim 性能复现脚本模板.

使用方式:
1. 复制本文件到 `.tmp/repro/<topic>/repro-<topic>.py`
2. 按需修改 `TOPIC`, `ROWS`, `FIELDS` 等常量
3. 确保 scalim 可导入: `uv run python .tmp/repro/<topic>/repro-<topic>.py`
4. 输出到 `.tmp/evidence/<topic>/<timestamp>/result.json`
"""

import argparse
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _get_rss_kb() -> int:
    """Linux-only RSS 采样."""
    try:
        with open("/proc/self/statm", "r") as f:
            parts = f.read().strip().split()
        if not parts:
            return 0
        rss_pages = int(parts[1])
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(rss_pages * page_size / 1024)
    except Exception:
        return 0


def _run_case(
    *,
    run_fn: Callable[[], Any],
    label: str,
) -> Dict[str, Any]:
    """运行一次测试 case，记录耗时与 RSS."""
    rss_before = _get_rss_kb()
    t0 = time.perf_counter()
    run_fn()
    t1 = time.perf_counter()
    rss_after = _get_rss_kb()
    return {
        "label": label,
        "rss_kb_before": rss_before,
        "rss_kb_after": rss_after,
        "duration_s": t1 - t0,
    }


# ---------------------------------------------------------------------------
# Baseline: 当前实现
# ---------------------------------------------------------------------------

# TODO: 填写 baseline 实现


def _baseline() -> None:
    """baseline 路径 — 使用当前框架代码."""
    raise NotImplementedError("fill in baseline run")


# ---------------------------------------------------------------------------
# Optimized: 实验性优化
# ---------------------------------------------------------------------------

# TODO: 填写 optimized 实现


def _optimized() -> None:
    """optimized 路径 — 拷贝/修改相关代码用于 A/B 对比."""
    raise NotImplementedError("fill in optimized run")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Scalim perf repro template")
    parser.add_argument("--out-dir", type=str, default=os.path.join(".tmp", "evidence", "TOPIC"))
    parser.add_argument("--runs", type=int, default=1, help="每项跑几次（取中位数）")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    results = []
    for i in range(args.runs):
        results.append(_run_case(run_fn=_baseline, label="baseline"))
        results.append(_run_case(run_fn=_optimized, label="optimized"))

    report = {
        "topic": "TOPIC",
        "runs": args.runs,
        "results": results,
    }

    report_path = os.path.join(args.out_dir, "result.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("report -> {}".format(report_path))


if __name__ == "__main__":
    main()
