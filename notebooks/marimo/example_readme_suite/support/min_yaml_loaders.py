"""最小 YAML 示例的假 loader。"""

from __future__ import annotations

from typing import Any, Dict, List


def load_orders(**_kwargs: Any) -> List[Dict[str, Any]]:
    return [
        {"order_id": 1, "amount": 10.0, "pay_id": "p1"},
        {"order_id": 2, "amount": 20.5, "pay_id": "p2"},
        {"order_id": 3, "amount": 7.0, "pay_id": "p1"},
    ]


def load_payments(**_kwargs: Any) -> Dict[str, Dict[str, Any]]:
    return {
        "p1": {"id": "p1", "payment_method": "card"},
        "p2": {"id": "p2", "payment_method": "cash"},
    }
