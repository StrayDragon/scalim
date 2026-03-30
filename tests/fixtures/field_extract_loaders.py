from typing import Any, Dict, Iterable, Mapping, Optional, Set


def load_orders(**_kwargs: Any) -> Iterable[Dict[Any, Any]]:
    # Main source rows; framework assigns row_id.
    return [
        {
            "order_id": 1,
            "payload": {"CustomerMark": {"clearn_reason_level": 2}},
            "list_payload": [{"x": 0}, {"x": 1}],
            "a.b": {"x": 123},
            "1": {"x": 1},
            1: {"x": 2},
        },
        {
            "order_id": 2,
            "payload": {"CustomerMark": {"clearn_reason_level": 3}},
            "list_payload": [{"x": 0}, {"x": 1}],
            "a.b": {"x": 456},
            "1": {"x": 10},
            1: {"x": 20},
        },
    ]


def load_clearn_reasons(*, order_id_set: Optional[Set[int]] = None, **_kwargs: Any) -> Mapping[int, Dict[Any, Any]]:
    ids = order_id_set or set()
    result: Dict[int, Dict[Any, Any]] = {}
    for order_id in ids:
        result[order_id] = {
            1: {"clearn_reason_level": int(order_id) + 1},
            2: {"clearn_reason_level": int(order_id) + 10},
            "review_status": 0,
        }
    return result


__all__ = [
    "load_clearn_reasons",
    "load_orders",
]
