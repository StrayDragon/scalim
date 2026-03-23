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


def test_preload_cache_get_or_load_does_not_call_load_fn_if_cached_before_acquiring_lock() -> None:
    cache = PreloadCache()
    original_lock_for = cache._lock_for  # type: ignore[attr-defined]
    calls = []

    def _lock_for_with_side_effect(source_id: str) -> threading.Lock:
        cache._data[source_id] = {1: {"value": "cached"}}  # type: ignore[attr-defined]
        return original_lock_for(source_id)

    cache._lock_for = _lock_for_with_side_effect  # type: ignore[assignment]

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
        return {1: {"value": "loaded"}}

    assert cache.get_or_load("src", _load) == {1: {"value": "cached"}}
    assert len(calls) == 0


def test_preload_cache_get_or_load_propagates_exceptions_to_waiters_and_allows_retry() -> None:
    cache = PreloadCache()
    barrier = threading.Barrier(2)
    calls = []
    errors = []

    class _LoadError(RuntimeError):
        pass

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
        time.sleep(0.05)
        raise _LoadError("boom")

    def _worker() -> None:
        try:
            barrier.wait(timeout=_TIMEOUT_S)
        except threading.BrokenBarrierError as exc:
            raise RuntimeError("timeout waiting for barrier") from exc
        try:
            cache.get_or_load("src", _load)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=_TIMEOUT_S)
    t2.join(timeout=_TIMEOUT_S)
    assert not t1.is_alive()
    assert not t2.is_alive()

    assert len(calls) == 1
    assert len(errors) == 2
    assert type(errors[0]) is type(errors[1]) is _LoadError
    assert str(errors[0]) == str(errors[1]) == "boom"
    assert "src" not in cache

    calls.clear()

    def _load_ok():  # type: ignore[no-untyped-def]
        calls.append(1)
        return {1: {"value": "ok"}}

    assert cache.get_or_load("src", _load_ok) == {1: {"value": "ok"}}
    assert cache.get_or_load("src", _load_ok) == {1: {"value": "ok"}}
    assert len(calls) == 1


def test_preload_cache_get_or_load_detects_recursive_same_key_and_does_not_deadlock() -> None:
    cache = PreloadCache()

    def _load():  # type: ignore[no-untyped-def]
        return cache.get_or_load("src", _load)

    try:
        cache.get_or_load("src", _load)
    except RuntimeError as exc:
        assert "recursive preload" in str(exc).lower()
    else:
        raise AssertionError("expected RuntimeError for recursive preload")

    calls = []

    def _load_ok():  # type: ignore[no-untyped-def]
        calls.append(1)
        return {1: {"value": "ok"}}

    assert cache.get_or_load("src", _load_ok) == {1: {"value": "ok"}}
    assert len(calls) == 1


def test_preload_cache_inflight_wait_falls_back_to_inflight_value_when_data_missing() -> None:
    from scalim.execution import preload_cache as preload_cache_module

    cache = PreloadCache()
    inflight = preload_cache_module._InFlight(owner_ident=123)  # type: ignore[attr-defined]
    inflight.value = {1: {"value": "x"}}
    inflight.done.set()
    cache._inflight["src"] = inflight  # type: ignore[attr-defined]

    def _load():  # type: ignore[no-untyped-def]
        raise AssertionError("load_fn should not be called")

    assert cache.get_or_load("src", _load) == {1: {"value": "x"}}


def test_preload_cache_inflight_wait_raises_clear_internal_error_if_done_without_value_or_error() -> None:
    from scalim.execution import preload_cache as preload_cache_module

    cache = PreloadCache()
    inflight = preload_cache_module._InFlight(owner_ident=123)  # type: ignore[attr-defined]
    inflight.done.set()
    cache._inflight["src"] = inflight  # type: ignore[attr-defined]

    def _load():  # type: ignore[no-untyped-def]
        raise AssertionError("load_fn should not be called")

    try:
        cache.get_or_load("src", _load)
    except RuntimeError as exc:
        assert "missing value/error" in str(exc).lower()
    else:
        raise AssertionError("expected RuntimeError for inflight done but missing value/error")


def test_preload_cache_clone_exception_for_reraise_exercises_fallbacks() -> None:
    from scalim.execution import preload_cache as preload_cache_module

    # copy.copy path
    e1 = ValueError("x")
    c1 = preload_cache_module._clone_exception_for_reraise(e1)  # type: ignore[attr-defined]
    assert isinstance(c1, BaseException)
    assert type(c1) is ValueError
    assert c1 is not e1

    # ctor fallback path (copy fails)
    class _UncopyableError(Exception):
        def __reduce__(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("nope")

    e2 = _UncopyableError("y")
    c2 = preload_cache_module._clone_exception_for_reraise(e2)  # type: ignore[attr-defined]
    assert isinstance(c2, BaseException)
    assert type(c2) is _UncopyableError
    assert c2 is not e2

    # final fallback path (copy fails + ctor fails)
    class _BadCtorError(Exception):
        def __reduce__(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("nope")

        def __init__(self):  # type: ignore[no-untyped-def]
            super(_BadCtorError, self).__init__("bad")

    e3 = _BadCtorError()
    c3 = preload_cache_module._clone_exception_for_reraise(e3)  # type: ignore[attr-defined]
    assert c3 is e3


def test_preload_cache_owner_error_path_tolerates_unexpected_with_traceback_failure() -> None:
    cache = PreloadCache()

    class _BadWithTracebackError(Exception):
        def with_traceback(self, tb):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    def _load():  # type: ignore[no-untyped-def]
        raise _BadWithTracebackError("x")

    try:
        cache.get_or_load("src", _load)
    except _BadWithTracebackError:
        pass
    else:
        raise AssertionError("expected _BadWithTracebackError")
