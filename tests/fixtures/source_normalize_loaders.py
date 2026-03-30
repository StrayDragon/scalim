CALL_COUNTS = {
    "orders": 0,
    "recommends": 0,
}


def reset_call_counts() -> None:
    CALL_COUNTS["orders"] = 0
    CALL_COUNTS["recommends"] = 0


def load_orders_main():
    CALL_COUNTS["orders"] += 1
    return [{"order_id": 101}, {"order_id": 102}]


def load_recommends_list():
    CALL_COUNTS["recommends"] += 1
    return [
        {"order_id": 101, "payload": {"score": 0.9}},
        {"order_id": 102, "payload": {"score": 0.7}},
    ]
