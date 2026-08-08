# -*- coding: utf-8 -*-
"""Workload shape presets (counts only; no business strings)."""
from __future__ import print_function

import os
from typing import Any, Dict

# Soft memory budget: 90% of currently available RAM at harness start.
_USABLE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".usable_bytes")


def usable_bytes() -> int:
    # type: () -> int
    try:
        with open(_USABLE_PATH, "r") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        # Fallback estimate if file missing: 8 GiB soft cap.
        return 8 * 1024 * 1024 * 1024


def shape_for(scale):
    # type: (str) -> Dict[str, Any]
    scale = str(scale or "smoke").strip().lower()
    usable = usable_bytes()
    usable_gb = round(usable / (1024.0 ** 3), 2)

    if scale == "smoke":
        return {
            "name": "smoke",
            "fact_rows": 10000,
            "dim_rows": 2000,
            "region_rows": 50,
            "batch_size": 500,
            "parallel_mode": "seq",
            "mem_soft_cap_bytes": usable,
            "mem_soft_cap_gb": usable_gb,
            "notes": "fast contract + sampling matrix",
        }
    if scale == "mid":
        return {
            "name": "mid",
            "fact_rows": 200000,
            "dim_rows": 20000,
            "region_rows": 200,
            "batch_size": 2000,
            "parallel_mode": "seq",
            "mem_soft_cap_bytes": usable,
            "mem_soft_cap_gb": usable_gb,
            "notes": "stage/loader layering visible",
        }
    if scale == "stress":
        # Excel write dominates wall time; keep under soft cap with practical runtime.
        # ~1e6 facts ≈ strong pressure without multi-hour sheet writes.
        target_bytes = int(usable * 0.45)
        fact_rows = max(400000, min(int(target_bytes / 8000), 1000000))
        dim_rows = max(40000, fact_rows // 10)
        return {
            "name": "stress",
            "fact_rows": int(fact_rows),
            "dim_rows": int(dim_rows),
            "region_rows": 500,
            "batch_size": 5000,
            "parallel_mode": "seq",
            "mem_soft_cap_bytes": usable,
            "mem_soft_cap_gb": usable_gb,
            "notes": "capped for practical Excel write time; soft cap=90% avail RAM at start",
        }
    raise ValueError("unknown scale {!r}; expected smoke|mid|stress".format(scale))
