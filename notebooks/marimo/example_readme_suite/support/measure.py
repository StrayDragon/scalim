"""本地 RSS 增量代理（无新依赖；Linux `/proc`；其它平台回退 0）。"""

from __future__ import annotations

import os
from typing import Callable, Dict


def rss_kb() -> int:
    try:
        with open("/proc/self/statm", "r") as handle:
            parts = handle.read().strip().split()
        if len(parts) < 2:
            return 0
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return int(int(parts[1]) * page_size / 1024)
    except (OSError, ValueError, AttributeError):
        return 0


def measure_rss_delta_kb(run_fn: Callable[[], object]) -> Dict[str, object]:
    before = rss_kb()
    result = run_fn()
    after = rss_kb()
    # 粗粒度代理：只比较运行前后 RSS，不在运行过程中采样峰值。
    delta = max(0, after - before)
    return {
        "rss_kb_before": before,
        "rss_kb_after": after,
        "rss_kb_delta": delta,
        "result": result,
    }
