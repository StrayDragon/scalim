import threading
from decimal import Decimal
from typing import Dict, Iterable, Mapping, Optional

from tests.support.testing_utils import CI_TIMEOUT_S, barrier_wait, event_wait


_LOCK = threading.Lock()
_PRELOAD_CALLS = 0

_MAIN_SLOW_RELEASE = threading.Event()
_MAIN_VERY_SLOW_RELEASE = threading.Event()
_PRELOAD_RELEASE = threading.Event()
_TABLE_C_RELEASE = threading.Event()
_FIRST_PRELOAD_ENTERED = threading.Event()
_MAIN_SLOW_ENTERED = threading.Event()

_MAIN_SLOW_BARRIER = None  # type: Optional[threading.Barrier]


def reset_timing() -> None:
    """Open all loader timing gates (non-blocking default) and clear barriers."""
    global _MAIN_SLOW_BARRIER
    _MAIN_SLOW_RELEASE.set()
    _MAIN_VERY_SLOW_RELEASE.set()
    _PRELOAD_RELEASE.set()
    _TABLE_C_RELEASE.set()
    _FIRST_PRELOAD_ENTERED.clear()
    _MAIN_SLOW_ENTERED.clear()
    _MAIN_SLOW_BARRIER = None


def reset_counters() -> None:
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS = 0
    reset_timing()


def preload_calls() -> int:
    with _LOCK:
        return int(_PRELOAD_CALLS)


def wait_first_preload_entered(*, timeout_s: float = CI_TIMEOUT_S) -> None:
    event_wait(_FIRST_PRELOAD_ENTERED, timeout_s=timeout_s, label="workflow_loaders.first_preload_entered")


def wait_main_slow_entered(*, timeout_s: float = CI_TIMEOUT_S) -> None:
    event_wait(_MAIN_SLOW_ENTERED, timeout_s=timeout_s, label="workflow_loaders.main_slow_entered")


def hold_main_slow() -> None:
    _MAIN_SLOW_RELEASE.clear()


def release_main_slow() -> None:
    _MAIN_SLOW_RELEASE.set()


def hold_main_very_slow() -> None:
    _MAIN_VERY_SLOW_RELEASE.clear()


def release_main_very_slow() -> None:
    _MAIN_VERY_SLOW_RELEASE.set()


def hold_preload() -> None:
    _PRELOAD_RELEASE.clear()


def release_preload() -> None:
    _PRELOAD_RELEASE.set()


def hold_table_c() -> None:
    _TABLE_C_RELEASE.clear()


def release_table_c() -> None:
    _TABLE_C_RELEASE.set()


def set_main_slow_barrier(*, parties: int) -> None:
    """Optional barrier rendezvous inside ``load_main_slow`` (after the release gate)."""
    global _MAIN_SLOW_BARRIER
    _MAIN_SLOW_BARRIER = threading.Barrier(int(parties))


def load_main_fast() -> Iterable[Mapping[str, object]]:
    return [{"ref_id": 1}]


def load_main_fast_releasing_very_slow() -> Iterable[Mapping[str, object]]:
    """Fast main loader that releases ``load_main_very_slow`` (for pipeline overlap tests)."""
    release_main_very_slow()
    return [{"ref_id": 1}]


def load_main_slow() -> Iterable[Mapping[str, object]]:
    _MAIN_SLOW_ENTERED.set()
    event_wait(_MAIN_SLOW_RELEASE, timeout_s=CI_TIMEOUT_S, label="workflow_loaders.main_slow")
    barrier = _MAIN_SLOW_BARRIER
    if barrier is not None:
        barrier_wait(barrier, timeout_s=CI_TIMEOUT_S, label="workflow_loaders.main_slow_barrier")
    return [{"ref_id": 1}]


def load_main_very_slow() -> Iterable[Mapping[str, object]]:
    event_wait(_MAIN_VERY_SLOW_RELEASE, timeout_s=CI_TIMEOUT_S, label="workflow_loaders.main_very_slow")
    return [{"ref_id": 1}]


def load_main_raises() -> Iterable[Mapping[str, object]]:
    raise ValueError("boom")


def load_preload_table(**kwargs: object) -> Dict[int, Mapping[str, object]]:
    _ = kwargs
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS += 1
        calls = int(_PRELOAD_CALLS)
    if calls == 1:
        _FIRST_PRELOAD_ENTERED.set()
    event_wait(_PRELOAD_RELEASE, timeout_s=CI_TIMEOUT_S, label="workflow_loaders.preload_table")
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


def load_formula_like_rows() -> Iterable[Mapping[str, object]]:
    """供 `allow_formulas=false` 导出转义对拍: 含公式前缀字符串."""

    return [
        {"label": "ok", "payload": "=1+1"},
        {"label": "sum", "payload": "  +SUM(A1:A2)"},
        {"label": "at", "payload": "@X"},
    ]


def load_table_b_fast() -> Iterable[Mapping[str, object]]:
    return [
        {"id": "b1", "value": "B1"},
        {"id": "b2", "value": "B2"},
    ]


def load_table_c_slow() -> Iterable[Mapping[str, object]]:
    event_wait(_TABLE_C_RELEASE, timeout_s=CI_TIMEOUT_S, label="workflow_loaders.table_c")
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


def load_table_temporal_values() -> Iterable[Mapping[str, object]]:
    from datetime import date, datetime, time, timedelta

    return [
        {
            "order_id": 1001,
            "created": datetime(2024, 1, 2, 3, 4, 5),
            "day": date(2024, 1, 2),
            "clock": time(3, 4, 5),
            "span": timedelta(days=1, seconds=30),
            "label": "ok",
        }
    ]


def load_table_aware_datetime() -> Iterable[Mapping[str, object]]:
    from datetime import datetime, timezone

    return [
        {
            "created": datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        }
    ]


reset_timing()
