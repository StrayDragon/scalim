import logging
import pickle
import threading

import pytest

from scalim.execution.preload_cache import PreloadCache, PreloadCacheSignatureGuardrail, PreloadCacheWaitDiagnostics

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

    restored.__setstate__({"_data": [], "_signature_digests": []})  # type: ignore[attr-defined]
    assert len(restored) == 0


def test_preload_cache_get_or_load_returns_cached_value_inside_lock() -> None:
    cache = PreloadCache()
    barrier = threading.Barrier(2)
    calls = []

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
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


def test_preload_cache_wait_diagnostics_default_disabled_emits_no_warning(caplog) -> None:
    cache = PreloadCache()
    calls = []
    owner_entered = threading.Event()
    allow_finish = threading.Event()
    results = []
    errors = []

    def _load_owner():  # type: ignore[no-untyped-def]
        calls.append(1)
        owner_entered.set()
        if not allow_finish.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for allow_finish")
        return {1: {"value": "z"}}

    def _load_waiter():  # type: ignore[no-untyped-def]
        raise AssertionError("load_fn should not be called for waiter")

    def _owner() -> None:
        try:
            results.append(cache.get_or_load("src", _load_owner))
        except BaseException as exc:
            errors.append(exc)

    def _waiter() -> None:
        try:
            if not owner_entered.wait(timeout=_TIMEOUT_S):
                raise RuntimeError("timeout waiting for owner_entered")
            results.append(cache.get_or_load("src", _load_waiter))
        except BaseException as exc:
            errors.append(exc)

    caplog.set_level(logging.WARNING, logger="scalim.preload-cache")
    t1 = threading.Thread(target=_owner)
    t2 = threading.Thread(target=_waiter)
    t1.start()
    t2.start()
    if not owner_entered.wait(timeout=_TIMEOUT_S):
        raise RuntimeError("timeout waiting for owner_entered")
    allow_finish.set()
    t1.join(timeout=_TIMEOUT_S)
    t2.join(timeout=_TIMEOUT_S)
    assert not t1.is_alive()
    assert not t2.is_alive()

    if errors:
        raise AssertionError(errors)
    assert results == [{1: {"value": "z"}}, {1: {"value": "z"}}]
    assert len(calls) == 1
    assert [rec for rec in caplog.records if rec.name == "scalim.preload-cache"] == []


def test_preload_cache_wait_diagnostics_emits_warning_with_stable_fields(caplog) -> None:
    warning_emitted = threading.Event()
    cache = PreloadCache(
        wait_diagnostics=PreloadCacheWaitDiagnostics(
            enabled=True,
            warn_after_s=0.0,
            repeat_every_s=None,
        ),
    )
    calls = []
    owner_entered = threading.Event()
    allow_finish = threading.Event()
    results = []
    errors = []

    logger = logging.getLogger("scalim.preload-cache")

    class _WarningHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if "inflight wait slow:" in record.getMessage():
                warning_emitted.set()

    handler = _WarningHandler()
    logger.addHandler(handler)
    try:

        def _load_owner():  # type: ignore[no-untyped-def]
            calls.append(1)
            owner_entered.set()
            if not allow_finish.wait(timeout=_TIMEOUT_S):
                raise RuntimeError("timeout waiting for allow_finish")
            return {1: {"value": "z"}}

        def _load_waiter():  # type: ignore[no-untyped-def]
            raise AssertionError("load_fn should not be called for waiter")

        def _owner() -> None:
            try:
                results.append(cache.get_or_load("src", _load_owner))
            except BaseException as exc:
                errors.append(exc)

        def _waiter() -> None:
            try:
                if not owner_entered.wait(timeout=_TIMEOUT_S):
                    raise RuntimeError("timeout waiting for owner_entered")
                results.append(cache.get_or_load("src", _load_waiter))
            except BaseException as exc:
                errors.append(exc)

        caplog.set_level(logging.WARNING, logger="scalim.preload-cache")
        t1 = threading.Thread(target=_owner)
        t2 = threading.Thread(target=_waiter)
        t1.start()
        t2.start()
        if not warning_emitted.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for warning emission")
        allow_finish.set()
        t1.join(timeout=_TIMEOUT_S)
        t2.join(timeout=_TIMEOUT_S)
        assert not t1.is_alive()
        assert not t2.is_alive()
    finally:
        logger.removeHandler(handler)

    if errors:
        raise AssertionError(errors)
    assert results == [{1: {"value": "z"}}, {1: {"value": "z"}}]
    assert len(calls) == 1

    messages = [rec.getMessage() for rec in caplog.records if rec.name == "scalim.preload-cache"]
    assert any(msg.startswith("[scalim] preload-cache:") for msg in messages)
    assert any("source_id=src" in msg and "wait_s=" in msg for msg in messages)


def test_preload_cache_wait_diagnostics_rejects_invalid_config_values() -> None:
    with pytest.raises(ValueError, match="warn_after_s"):
        _ = PreloadCacheWaitDiagnostics(enabled=True, warn_after_s=-1.0)

    with pytest.raises(ValueError, match="repeat_every_s"):
        _ = PreloadCacheWaitDiagnostics(enabled=True, warn_after_s=0.1, repeat_every_s=0.0)


def test_preload_cache_signature_guardrail_rejects_invalid_policy_values() -> None:
    with pytest.raises(ValueError, match="policy"):
        _ = PreloadCacheSignatureGuardrail(enabled=True, policy="nope")


def test_preload_cache_signature_guardrail_enabled_property_reflects_config() -> None:
    assert PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail.disabled()).signature_guardrail_enabled is False
    assert (
        PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail(enabled=True, policy="error")).signature_guardrail_enabled is True
    )


def test_preload_cache_signature_guardrail_disabled_keeps_legacy_semantics() -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail.disabled())
    calls = []

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
        return {1: {"value": "y"}}

    first = cache.get_or_load("src", _load, signature_digest="a")
    second = cache.get_or_load("src", _load, signature_digest="b")
    assert first == {1: {"value": "y"}}
    assert second == {1: {"value": "y"}}
    assert len(calls) == 1


def test_preload_cache_signature_guardrail_populates_digest_for_preexisting_cached_value() -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail(enabled=True, policy="error"))
    cache._data["s1"] = {1: {"value": "cached"}}  # type: ignore[attr-defined]

    def _load_should_not_run():  # type: ignore[no-untyped-def]
        raise AssertionError("load_fn should not be called")

    assert cache.get_or_load("s1", _load_should_not_run, signature_digest="a") == {1: {"value": "cached"}}
    assert cache._signature_digests.get("s1") == "a"  # type: ignore[attr-defined]


def test_preload_cache_signature_guardrail_error_mode_fails_fast_on_mismatch() -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail(enabled=True, policy="error"))

    def _load():  # type: ignore[no-untyped-def]
        return {1: {"value": "y"}}

    _ = cache.get_or_load("s1", _load, signature_digest="a")
    with pytest.raises(RuntimeError) as excinfo:
        _ = cache.get_or_load("s1", _load, signature_digest="b")
    msg = str(excinfo.value)
    assert "source_id=s1" in msg
    assert "cached_digest=a" in msg
    assert "requested_digest=b" in msg


def test_preload_cache_signature_guardrail_inflight_rejects_mismatched_digest() -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail(enabled=True, policy="error"))
    owner_started = threading.Event()
    allow_finish = threading.Event()
    owner_result = []
    waiter_error = []

    def _load_owner():  # type: ignore[no-untyped-def]
        owner_started.set()
        if not allow_finish.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for allow_finish")
        return {1: {"value": "y"}}

    def _owner() -> None:
        owner_result.append(cache.get_or_load("s1", _load_owner, signature_digest="a"))

    def _waiter() -> None:
        if not owner_started.wait(timeout=_TIMEOUT_S):
            waiter_error.append(RuntimeError("timeout waiting for owner_started"))
            return

        def _load_should_not_run():  # type: ignore[no-untyped-def]
            raise AssertionError("load_fn should not be called")

        try:
            _ = cache.get_or_load("s1", _load_should_not_run, signature_digest="b")
        except Exception as exc:  # noqa: BLE001
            waiter_error.append(exc)

    t1 = threading.Thread(target=_owner)
    t2 = threading.Thread(target=_waiter)
    t1.start()
    t2.start()
    t2.join(timeout=_TIMEOUT_S)
    assert not t2.is_alive()

    allow_finish.set()
    t1.join(timeout=_TIMEOUT_S)
    assert not t1.is_alive()

    assert owner_result == [{1: {"value": "y"}}]
    assert len(waiter_error) == 1
    assert isinstance(waiter_error[0], RuntimeError)
    assert "cached_digest=a" in str(waiter_error[0])
    assert "requested_digest=b" in str(waiter_error[0])


def test_preload_cache_signature_guardrail_inflight_accepts_first_digest_when_inflight_has_none() -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail.disabled())
    owner_started = threading.Event()
    allow_finish = threading.Event()
    waiter_called = threading.Event()
    waiter_entered = threading.Event()
    waiter_result = []

    def _load_owner():  # type: ignore[no-untyped-def]
        owner_started.set()
        if not waiter_called.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for waiter_called")
        if not allow_finish.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for allow_finish")
        return {1: {"value": "y"}}

    def _owner() -> None:
        _ = cache.get_or_load("s1", _load_owner)

    def _waiter() -> None:
        if not owner_started.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for owner_started")
        waiter_called.set()

        def _load_should_not_run():  # type: ignore[no-untyped-def]
            raise AssertionError("load_fn should not be called")

        waiter_result.append(cache.get_or_load("s1", _load_should_not_run, signature_digest="a"))

    t1 = threading.Thread(target=_owner)
    t2 = threading.Thread(target=_waiter)
    t1.start()
    if not owner_started.wait(timeout=_TIMEOUT_S):
        raise RuntimeError("timeout waiting for owner_started")

    cache._signature_guardrail = PreloadCacheSignatureGuardrail(enabled=True, policy="error")  # type: ignore[attr-defined]

    original_waiter = cache._get_or_load_waiter  # type: ignore[attr-defined]

    def _wrapped_waiter(*args, **kwargs):  # type: ignore[no-untyped-def]
        waiter_entered.set()
        return original_waiter(*args, **kwargs)

    cache._get_or_load_waiter = _wrapped_waiter  # type: ignore[assignment]

    t2.start()

    if not waiter_entered.wait(timeout=_TIMEOUT_S):
        raise RuntimeError("timeout waiting for waiter to join inflight")

    allow_finish.set()
    t2.join(timeout=_TIMEOUT_S)
    t1.join(timeout=_TIMEOUT_S)
    assert not t2.is_alive()
    assert not t1.is_alive()
    assert waiter_result == [{1: {"value": "y"}}]


def test_preload_cache_signature_guardrail_warn_mode_emits_warning_and_continues(caplog) -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail(enabled=True, policy="warn"))

    def _load():  # type: ignore[no-untyped-def]
        return {1: {"value": "y"}}

    caplog.set_level(logging.WARNING, logger="scalim.preload-cache")
    _ = cache.get_or_load("s1", _load, signature_digest="a")

    def _load_should_not_run():  # type: ignore[no-untyped-def]
        raise AssertionError("load_fn should not be called")

    out = cache.get_or_load("s1", _load_should_not_run, signature_digest="b")
    assert out == {1: {"value": "y"}}

    messages = [rec.getMessage() for rec in caplog.records if rec.name == "scalim.preload-cache"]
    assert any("signature digest mismatch" in msg for msg in messages)
    assert any("source_id=s1" in msg and "cached_digest=a" in msg and "requested_digest=b" in msg for msg in messages)


def test_preload_cache_signature_guardrail_enabled_requires_signature_digest() -> None:
    cache = PreloadCache(signature_guardrail=PreloadCacheSignatureGuardrail(enabled=True, policy="error"))

    def _load():  # type: ignore[no-untyped-def]
        return {1: {"value": "y"}}

    with pytest.raises(ValueError, match="signature_digest"):
        _ = cache.get_or_load("s1", _load)


def test_preload_cache_wait_diagnostics_repeat_emits_multiple_warnings(caplog) -> None:
    warnings_emitted = threading.Event()
    warning_count = {"n": 0}
    cache = PreloadCache(
        wait_diagnostics=PreloadCacheWaitDiagnostics(
            enabled=True,
            warn_after_s=0.0,
            repeat_every_s=0.05,
        ),
    )
    owner_entered = threading.Event()
    allow_finish = threading.Event()
    errors = []

    logger = logging.getLogger("scalim.preload-cache")

    class _WarningHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if "inflight wait slow:" not in record.getMessage():
                return
            warning_count["n"] += 1
            if warning_count["n"] >= 2:
                warnings_emitted.set()

    handler = _WarningHandler()
    logger.addHandler(handler)
    try:

        def _load_owner():  # type: ignore[no-untyped-def]
            owner_entered.set()
            if not allow_finish.wait(timeout=_TIMEOUT_S):
                raise RuntimeError("timeout waiting for allow_finish")
            return {1: {"value": "z"}}

        def _load_waiter():  # type: ignore[no-untyped-def]
            raise AssertionError("load_fn should not be called for waiter")

        def _owner() -> None:
            try:
                _ = cache.get_or_load("src", _load_owner)
            except BaseException as exc:
                errors.append(exc)

        def _waiter() -> None:
            try:
                if not owner_entered.wait(timeout=_TIMEOUT_S):
                    raise RuntimeError("timeout waiting for owner_entered")
                _ = cache.get_or_load("src", _load_waiter)
            except BaseException as exc:
                errors.append(exc)

        caplog.set_level(logging.WARNING, logger="scalim.preload-cache")
        t1 = threading.Thread(target=_owner)
        t2 = threading.Thread(target=_waiter)
        t1.start()
        t2.start()
        if not warnings_emitted.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for multiple warning emissions")
        allow_finish.set()
        t1.join(timeout=_TIMEOUT_S)
        t2.join(timeout=_TIMEOUT_S)
        assert not t1.is_alive()
        assert not t2.is_alive()
    finally:
        logger.removeHandler(handler)

    if errors:
        raise AssertionError(errors)
    assert warning_count["n"] >= 2
    messages = [rec.getMessage() for rec in caplog.records if rec.name == "scalim.preload-cache"]
    slow_warnings = [msg for msg in messages if "inflight wait slow:" in msg]
    assert len(slow_warnings) >= 2


def test_preload_cache_wait_diagnostics_capture_owner_callsite_includes_callsite(caplog) -> None:
    warning_emitted = threading.Event()
    cache = PreloadCache(
        wait_diagnostics=PreloadCacheWaitDiagnostics(
            enabled=True,
            warn_after_s=0.0,
            repeat_every_s=None,
            capture_owner_callsite=True,
        ),
    )
    owner_entered = threading.Event()
    allow_finish = threading.Event()
    errors = []

    logger = logging.getLogger("scalim.preload-cache")

    class _WarningHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if "owner_callsite=" in record.getMessage():
                warning_emitted.set()

    handler = _WarningHandler()
    logger.addHandler(handler)
    try:

        def _load_owner():  # type: ignore[no-untyped-def]
            owner_entered.set()
            if not allow_finish.wait(timeout=_TIMEOUT_S):
                raise RuntimeError("timeout waiting for allow_finish")
            return {1: {"value": "z"}}

        def _load_waiter():  # type: ignore[no-untyped-def]
            raise AssertionError("load_fn should not be called for waiter")

        def _owner() -> None:
            try:
                _ = cache.get_or_load("src", _load_owner)
            except BaseException as exc:
                errors.append(exc)

        def _waiter() -> None:
            try:
                if not owner_entered.wait(timeout=_TIMEOUT_S):
                    raise RuntimeError("timeout waiting for owner_entered")
                _ = cache.get_or_load("src", _load_waiter)
            except BaseException as exc:
                errors.append(exc)

        caplog.set_level(logging.WARNING, logger="scalim.preload-cache")
        t1 = threading.Thread(target=_owner)
        t2 = threading.Thread(target=_waiter)
        t1.start()
        t2.start()
        if not warning_emitted.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for warning emission")
        allow_finish.set()
        t1.join(timeout=_TIMEOUT_S)
        t2.join(timeout=_TIMEOUT_S)
        assert not t1.is_alive()
        assert not t2.is_alive()
    finally:
        logger.removeHandler(handler)

    if errors:
        raise AssertionError(errors)
    messages = [rec.getMessage() for rec in caplog.records if rec.name == "scalim.preload-cache"]
    assert any("owner_callsite=" in msg for msg in messages)


def test_preload_cache_capture_owner_callsite_falls_back_to_unknown_when_stack_filtered(monkeypatch) -> None:
    import traceback as std_traceback

    from scalim.execution import preload_cache as mod

    def _fake_extract_stack(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return [
            std_traceback.FrameSummary("preload_cache.py", 1, "f1"),
            std_traceback.FrameSummary("preload_cache.py", 2, "f2"),
        ]

    monkeypatch.setattr(mod.traceback, "extract_stack", _fake_extract_stack)
    assert mod._capture_owner_callsite() == "(unknown)"  # type: ignore[attr-defined]


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
    calls = []
    errors = []
    owner_entered = threading.Event()
    allow_raise = threading.Event()

    class _LoadError(RuntimeError):
        pass

    def _load_owner():  # type: ignore[no-untyped-def]
        calls.append(1)
        owner_entered.set()
        if not allow_raise.wait(timeout=_TIMEOUT_S):
            raise RuntimeError("timeout waiting for allow_raise")
        raise _LoadError("boom")

    def _load_waiter():  # type: ignore[no-untyped-def]
        raise AssertionError("load_fn should not be called for waiter")

    def _owner() -> None:
        try:
            cache.get_or_load("src", _load_owner)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def _waiter() -> None:
        if not owner_entered.wait(timeout=_TIMEOUT_S):
            errors.append(RuntimeError("timeout waiting for owner_entered"))
            return
        try:
            cache.get_or_load("src", _load_waiter)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_owner)
    t2 = threading.Thread(target=_waiter)
    t1.start()
    if not owner_entered.wait(timeout=_TIMEOUT_S):
        raise RuntimeError("timeout waiting for owner_entered")
    t2.start()
    allow_raise.set()
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
