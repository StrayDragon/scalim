from typing import Any, Dict, List


def demo_orders_loader(**_kwargs: Any) -> List[Dict[str, Any]]:
    # A tiny, deterministic dataset for YAML outputs end-to-end tests.
    return [
        {"order_id": "o1", "channel": "direct", "customer_id": "c1", "amount": 70},
        {"order_id": "o2", "channel": "direct", "customer_id": "c1", "amount": 50},
        {"order_id": "o3", "channel": "direct", "customer_id": "c2", "amount": 200},
        {"order_id": "o4", "channel": "direct", "customer_id": "c3", "amount": 200},
        # Should be excluded by `outputs.*.where` in both detail and aggregate outputs.
        {"order_id": "o5", "channel": "other", "customer_id": "c1", "amount": 999},
    ]


def score_from_rank(rank: int, *, base: int = 0, step: int = 1) -> int:
    # Mirrors `score_by_rank` semantics: base - (rank-1)*step.
    return int(base) - (int(rank) - 1) * int(step)
