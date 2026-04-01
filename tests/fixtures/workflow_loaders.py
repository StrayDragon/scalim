import threading
import time
from decimal import Decimal
from typing import Dict, Iterable, Mapping


_LOCK = threading.Lock()
_PRELOAD_CALLS = 0


def reset_counters() -> None:
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS = 0


def preload_calls() -> int:
    with _LOCK:
        return int(_PRELOAD_CALLS)


def load_main_fast() -> Iterable[Mapping[str, object]]:
    return [{"ref_id": 1}]


def load_main_slow() -> Iterable[Mapping[str, object]]:
    time.sleep(0.05)
    return [{"ref_id": 1}]


def load_main_raises() -> Iterable[Mapping[str, object]]:
    raise ValueError("boom")


def load_preload_table(**kwargs: object) -> Dict[int, Mapping[str, object]]:
    _ = kwargs
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS += 1
    time.sleep(0.05)
    return {1: {"id": 1, "value": "ok"}}


def load_preload_table_alt(**kwargs: object) -> Dict[int, Mapping[str, object]]:
    _ = kwargs
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS += 1
    return {1: {"id": 1, "value": "alt"}}


def load_table_a_fast() -> Iterable[Mapping[str, object]]:
    return [
        {"id": "a1", "value": "A1"},
        {"id": "a2", "value": "A2"},
    ]


def load_table_b_fast() -> Iterable[Mapping[str, object]]:
    return [
        {"id": "b1", "value": "B1"},
        {"id": "b2", "value": "B2"},
    ]


def load_table_c_slow() -> Iterable[Mapping[str, object]]:
    time.sleep(0.05)
    return [
        {"id": "c1", "value": "C1"},
    ]


def load_table_mismatch() -> Iterable[Mapping[str, object]]:
    return [
        {"id": "m1", "other": "X"},
    ]


def load_table_raises() -> Iterable[Mapping[str, object]]:
    raise ValueError("boom")


def load_table_typed_values() -> Iterable[Mapping[str, object]]:
    return [
        {
            "order_count": 5,
            "amount": Decimal("1.20"),
            "paid": True,
            "code": "007",
            "raw_text": "",
        }
    ]
