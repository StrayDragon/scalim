"""最小 YAML DSL 示例的假 loader (README 第一口 · 两源切片)。

对应 YAML: `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/min_report.yaml`
"""

from __future__ import annotations

from typing import Any

# 主源: 订单 (每行一条订单; pay_id 用于关联支付方式小表)


def load_orders(**_kwargs: Any) -> list[dict[str, Any]]:
    return [
        {"order_id": 1, "amount": 10.0, "pay_id": "p1"},
        {"order_id": 2, "amount": 20.5, "pay_id": "p2"},
        {"order_id": 3, "amount": 7.0, "pay_id": "p1"},
    ]


# 维表: 支付方式 (dict 形态 = 以 key 索引的 lookup 表)


def load_payments(**_kwargs: Any) -> dict[str, dict[str, Any]]:
    return {
        "p1": {"id": "p1", "payment_method": "card"},
        "p2": {"id": "p2", "payment_method": "cash"},
    }
