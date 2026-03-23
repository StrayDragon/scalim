import pickle
import threading
import time

from scalim.execution.preload_cache import PreloadCache

_TIMEOUT_S = 5.0


def test_preload_cache_supports_basic_mapping_protocol_and_pickle_roundtrip() -> None:
    cache = PreloadCache()
    assert len(cache) == 0

    cache["a"] = {1: {"value": "x"}}
    assert len(cache) == 1
    assert cache["a"][1]["value"] == "x"
    assert list(iter(cache)) == ["a"]

    del cache["a"]
    assert len(cache) == 0

    calls = []

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
        return {1: {"value": "y"}}

    first = cache.get_or_load("src", _load)
    second = cache.get_or_load("src", _load)
    assert first == {1: {"value": "y"}}
    assert second == {1: {"value": "y"}}
    assert len(calls) == 1

    data = pickle.dumps(cache)
    restored = pickle.loads(data)
    assert restored["src"] == {1: {"value": "y"}}

    restored.__setstate__({"_data": []})  # type: ignore[attr-defined]
    assert len(restored) == 0


def test_preload_cache_get_or_load_returns_cached_value_inside_lock() -> None:
    cache = PreloadCache()
    barrier = threading.Barrier(2)
    calls = []

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
        time.sleep(0.05)
        return {1: {"value": "z"}}

    results = []

    def _worker() -> None:
        try:
            barrier.wait(timeout=_TIMEOUT_S)
        except threading.BrokenBarrierError as exc:
            raise RuntimeError("timeout waiting for barrier") from exc
        results.append(cache.get_or_load("src", _load))

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=_TIMEOUT_S)
    t2.join(timeout=_TIMEOUT_S)
    assert not t1.is_alive()
    assert not t2.is_alive()

    assert results == [{1: {"value": "z"}}, {1: {"value": "z"}}]
    assert len(calls) == 1
