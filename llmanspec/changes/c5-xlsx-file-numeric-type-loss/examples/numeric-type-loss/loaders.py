"""脱敏支付报表场景的 loader 函数 — 镜像 Pay Order 的多 sheet 模式。

场景覆盖:
  1. 同一 xlsx_file book 多 sheet 写入 (明细 + 渠道维度 + 整体指标)
  2. 多 demand 流水线 (detail → channel → kpi)
  3. 多种数字类型: int, float, Decimal, bool, None, 零值
  4. 对比 xlsx_memory 路径的类型保留

本模块不包含任何真实业务数据。
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional


def to_numeric(value: Any) -> Any:
    """模仿 ET Pay Order 项目 loaders.to_numeric()。
    即使经过此函数确保类型正确，xlsx_file 路径仍会 str() 掉全部数字。
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def load_transactions(
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
    **_kwargs: Any,
) -> List[Dict[str, Any]]:
    """交易明细数据 — 对应 Pay Order 的"支付成功订单信息统计"sheet。

    覆盖的数字类型边界情况:
      - float: 1299.00, 0.0
      - int: 2, 0, 1
      - Decimal: Decimal('158.00')
      - bool: True, False
      - None: 可选字段缺失值
      - 零值: 0, 0.0
    """
    _ = field_keys, is_ref_loader
    return [
        # 正常数据
        {
            "tx_id": "T001",
            "product": "方案A",
            "amount": 1299.00,
            "rate": 0.85,
            "qty": 2,
            "unit_price": 649.50,
            "active": True,
            "discount": 0.15,
            "status": 1,
        },
        {
            "tx_id": "T002",
            "product": "方案B",
            "amount": 5800.00,
            "rate": 0.92,
            "qty": 1,
            "unit_price": 5800.00,
            "active": True,
            "discount": None,
            "status": 1,
        },
        {
            "tx_id": "T003",
            "product": "方案A",
            "amount": 2600.00,
            "rate": 0.78,
            "qty": 3,
            "unit_price": 866.67,
            "active": False,
            "discount": 0.05,
            "status": 2,
        },
        {
            "tx_id": "T004",
            "product": "方案C",
            "amount": 399.00,
            "rate": 0.95,
            "qty": 5,
            "unit_price": 79.80,
            "active": True,
            "discount": 0.0,
            "status": 1,
        },
        # 零值边界
        {
            "tx_id": "T005",
            "product": "方案B",
            "amount": 0.00,
            "rate": 0.88,
            "qty": 0,
            "unit_price": 0.00,
            "active": False,
            "discount": 0.0,
            "status": 3,
        },
        # None 字段
        {
            "tx_id": "T006",
            "product": "方案A",
            "amount": None,
            "rate": 0.90,
            "qty": 1,
            "unit_price": 999.00,
            "active": True,
            "discount": None,
            "status": 1,
        },
        # Decimal 类型
        {
            "tx_id": "T007",
            "product": "方案C",
            "amount": Decimal("158.00"),
            "rate": 0.87,
            "qty": 2,
            "unit_price": Decimal("79.00"),
            "active": True,
            "discount": Decimal("0.10"),
            "status": 2,
        },
        # 大数值
        {
            "tx_id": "T008",
            "product": "方案D",
            "amount": 99999.99,
            "rate": 0.75,
            "qty": 100,
            "unit_price": 999.99,
            "active": True,
            "discount": 0.20,
            "status": 1,
        },
    ]


def load_channel_summary(
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
    **_kwargs: Any,
) -> List[Dict[str, Any]]:
    """渠道维度聚合数据 — 对应 Pay Order 的维度 sheet。

    消费 load_transactions 的产出，按 product 作为"渠道"维度聚合。
    """
    _ = field_keys, is_ref_loader
    txs = load_transactions()
    aggs: Dict[str, Dict[str, Any]] = {}
    for tx in txs:
        if not tx.get("product"):
            continue
        prod = tx["product"]
        if prod not in aggs:
            aggs[prod] = {
                "order_count": 0,
                "total_amount": 0.0,
                "active_count": 0,
                "total_qty": 0,
            }
        aggs[prod]["order_count"] += 1
        aggs[prod]["total_amount"] += float(tx.get("amount") or 0)
        aggs[prod]["active_count"] += 1 if tx.get("active") else 0
        aggs[prod]["total_qty"] += tx.get("qty") or 0

    total_amount = sum(v["total_amount"] for v in aggs.values())
    result = []
    for prod, v in sorted(aggs.items()):
        oc = v["order_count"]
        result.append(
            {
                "channel": prod,
                "order_count": oc,
                "total_amount": round(v["total_amount"], 2),
                "avg_amount": round(v["total_amount"] / oc, 2) if oc else 0.0,
                "active_rate": round(v["active_count"] / oc * 100, 1) if oc else 0.0,
                "share_pct": round(v["total_amount"] / total_amount * 100, 2)
                if total_amount
                else 0.0,
                "total_qty": v["total_qty"],
            }
        )
    return result


def load_overall_kpi(
    field_keys: Optional[List[str]] = None,
    is_ref_loader: bool = False,
    **_kwargs: Any,
) -> List[Dict[str, Any]]:
    """整体 KPI 指标 — 对应 Pay Order 的汇总指标 sheet。

    消费 load_channel_summary 的产出，计算整体指标。
    """
    _ = field_keys, is_ref_loader
    channels = load_channel_summary()
    total_orders = sum(c["order_count"] for c in channels)
    total_amount = sum(c["total_amount"] for c in channels)
    total_qty = sum(c["total_qty"] for c in channels)
    active_orders = sum(
        c["active_rate"] * c["order_count"] / 100 for c in channels
    )

    return [
        {
            "metric": "总订单数",
            "value": float(total_orders),
            "unit": "笔",
            "target": 100.0,
            "attained": True,
        },
        {
            "metric": "总金额",
            "value": total_amount,
            "unit": "元",
            "target": 20000.0,
            "attained": total_amount >= 20000,
        },
        {
            "metric": "总数量",
            "value": float(total_qty),
            "unit": "件",
            "target": 50.0,
            "attained": total_qty >= 50,
        },
        {
            "metric": "活跃率",
            "value": round(active_orders / total_orders * 100, 1)
            if total_orders
            else 0.0,
            "unit": "%",
            "target": 80.0,
            "attained": False,
        },
        {
            "metric": "平均单价",
            "value": round(total_amount / total_qty, 2) if total_qty else 0.0,
            "unit": "元",
            "target": 500.0,
            "attained": True,
        },
    ]
