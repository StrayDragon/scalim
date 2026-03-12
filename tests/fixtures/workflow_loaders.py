import threading
import time
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


def load_preload_table() -> Dict[int, Mapping[str, object]]:
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS += 1
    time.sleep(0.05)
    return {1: {"id": 1, "value": "ok"}}


def load_preload_table_alt() -> Dict[int, Mapping[str, object]]:
    global _PRELOAD_CALLS
    with _LOCK:
        _PRELOAD_CALLS += 1
    return {1: {"id": 1, "value": "alt"}}
