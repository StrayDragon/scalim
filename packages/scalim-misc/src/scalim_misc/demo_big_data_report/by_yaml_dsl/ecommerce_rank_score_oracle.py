from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, load_orders, set_config
from scalim_misc.examples.oracle import diff_first_mismatch, stable_sort_rows

TOP_K = 2


def _to_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


@dataclass(frozen=True)
class _AggRow:
    region_id: int
    product_category_id: int
    order_cnt: int
    sum_final_amount: Decimal
    rank: int
    row_no: int
    score: Decimal


def build_expected_rows_top2_by_region(*, cfg: Optional[ECommerceConfig] = None) -> List[Dict[str, str]]:
    """构造 `ecommerce_rank_score_report.yaml` 的纯 Python 期望输出.

    说明:
    - 口径与 `src/scalim/execution/derived_outputs.py:RankedGroupByAggregator` 对齐:
      - `order: desc` 会对 `order_by` 中每个字段都使用同一方向排序
      - `dense_rank` 只按 `by` 字段判断并列
      - `row_number` 连续编号
      - `top_k_mode=rows` 截断为固定 K 行
    """
    prev = get_config()
    if cfg is not None:
        set_config(cfg)
    try:
        groups: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for row in load_orders():
            region_id = int(row.get("region_id") or 0)
            category_id = int(row.get("product_category_id") or 0)
            quantity = int(row.get("quantity") or 0)
            unit_price = float(row.get("unit_price") or 0.0)
            discount_rate = float(row.get("discount_rate") or 0.0)

            final_amount = float(quantity) * float(unit_price) * float(discount_rate)
            final_dec = Decimal(str(final_amount))

            key = (region_id, category_id)
            acc = groups.setdefault(
                key, {"region_id": region_id, "product_category_id": category_id, "order_cnt": 0, "sum_final_amount": Decimal(0)}
            )
            acc["order_cnt"] = int(acc["order_cnt"]) + 1
            acc["sum_final_amount"] = Decimal(str(acc["sum_final_amount"])) + final_dec

        by_region: Dict[int, List[Dict[str, Any]]] = {}
        for acc in groups.values():
            by_region.setdefault(int(acc["region_id"]), []).append(acc)

        ordered: List[_AggRow] = []
        for region_id in sorted(by_region.keys()):
            bucket = by_region[region_id]
            # 对齐 `RankedGroupByAggregator._row_sort_key` 的统一 `desc` 方向:
            # - sum_final_amount desc
            # - product_category_id desc (作为 tie-break)
            bucket.sort(key=lambda r: (Decimal(str(r["sum_final_amount"])), int(r["product_category_id"])), reverse=True)

            # 先计算 rank/row_number(全量),再按 row_number top_k 截断,最后计算 score.
            prev_sig: Optional[str] = None
            last_rank = 0
            for idx, r in enumerate(bucket):
                row_no = int(idx) + 1
                sum_amount = Decimal(str(r["sum_final_amount"]))
                sig = "num:" + format(sum_amount, "f")
                if idx == 0:
                    last_rank = 1
                elif prev_sig is None or sig != prev_sig:
                    last_rank += 1
                prev_sig = sig
                r["rank"] = int(last_rank)
                r["row_no"] = int(row_no)

            top2 = [r for r in bucket if int(r.get("row_no") or 0) <= TOP_K]
            for r in top2:
                rank_val = int(r["rank"])
                score = Decimal(100) - (Decimal(rank_val - 1) * Decimal(3))
                ordered.append(
                    _AggRow(
                        region_id=int(r["region_id"]),
                        product_category_id=int(r["product_category_id"]),
                        order_cnt=int(r["order_cnt"]),
                        sum_final_amount=Decimal(str(r["sum_final_amount"])),
                        rank=int(rank_val),
                        row_no=int(r["row_no"]),
                        score=score,
                    )
                )

        return [
            {
                "region_id": _to_csv_cell(r.region_id),
                "product_category_id": _to_csv_cell(r.product_category_id),
                "order_cnt": _to_csv_cell(r.order_cnt),
                "sum_final_amount": _to_csv_cell(r.sum_final_amount),
                "rank": _to_csv_cell(r.rank),
                "row_no": _to_csv_cell(r.row_no),
                "score": _to_csv_cell(r.score),
            }
            for r in ordered
        ]
    finally:
        if cfg is not None:
            set_config(prev)


def verify_ecommerce_rank_score_csv_rows(
    *,
    actual_rows: Sequence[Mapping[str, Any]],
    cfg: Optional[ECommerceConfig] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """逐行对拍 `ecommerce_rank_score_report` 的 CSV 输出."""
    expected_rows = build_expected_rows_top2_by_region(cfg=cfg)
    actual_sorted = stable_sort_rows(actual_rows, by=("region_id", "row_no", "product_category_id"))
    expected_sorted = stable_sort_rows(expected_rows, by=("region_id", "row_no", "product_category_id"))

    fields = ["region_id", "product_category_id", "order_cnt", "sum_final_amount", "rank", "row_no", "score"]
    ok, msg = diff_first_mismatch(actual_sorted, expected_sorted, fields=fields)
    details: Dict[str, Any] = {
        "actual": len(actual_sorted),
        "expected": len(expected_sorted),
        "first_mismatch": msg,
    }
    return bool(ok), str(msg), details


__all__ = [
    "build_expected_rows_top2_by_region",
    "verify_ecommerce_rank_score_csv_rows",
]
