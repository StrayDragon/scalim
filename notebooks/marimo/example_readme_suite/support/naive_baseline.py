"""Naive / 内存不友好基线：一次性物化宽表全部字段并常驻内存。"""

from __future__ import annotations

from typing import Any, Dict, List

from notebooks.marimo.example_readme_suite.support import knobs
from notebooks.marimo.example_readme_suite.support.measure import measure_rss_delta_kb


def build_wide_rows(n_rows: int, n_fields: int, payload_chars: int) -> List[Dict[str, Any]]:
    pad = "x" * int(payload_chars)
    rows: List[Dict[str, Any]] = []
    for i in range(int(n_rows)):
        row: Dict[str, Any] = {"order_id": i, "amount": float(i % 100)}
        for f in range(int(n_fields)):
            row["f{:03d}".format(f)] = "{}-{}-{}".format(i, f, pad)
        rows.append(row)
    return rows


def run_naive(*, n_rows: int = knobs.N_ROWS, n_fields: int = knobs.N_FIELDS, payload_chars: int = knobs.PAYLOAD_CHARS) -> Dict[str, Any]:
    """全量加载宽表，再做一次「全列 enrich 拷贝」（模拟急切物化）。"""

    def _body() -> Dict[str, Any]:
        rows = build_wide_rows(n_rows, n_fields, payload_chars)
        enriched = [dict(r) for r in rows]
        total_amount = sum(float(r["amount"]) for r in enriched)
        return {"rows": len(enriched), "fields": n_fields, "total_amount": total_amount}

    measured = measure_rss_delta_kb(_body)
    result = measured.pop("result")
    assert isinstance(result, dict)
    out = dict(result)
    out.update(measured)
    out["label"] = "naive"
    return out
