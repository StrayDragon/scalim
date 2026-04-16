from typing import Any, Dict, List, Optional, Tuple

import pytest

import scalim.execution.loader_retry as lr
from scalim.events import EventType
from scalim.execution.loader_retry import CALLSITE_LOAD, LoaderRetryContext, LoaderRetryPolicy, call_with_loader_retry


class _CaptureInstrumentation(object):
    def __init__(self, *, wants_retry: bool = True) -> None:
        self._wants_retry = bool(wants_retry)
        self.retry_events: List[Dict[str, Any]] = []
        self.error_events: List[Tuple[Exception, Dict[str, Any]]] = []

    def wants(self, event_type: str) -> bool:
        return bool(self._wants_retry and event_type == EventType.LOADER_RETRY)

    def emit_loader_retry(
        self,
        *,
        loader_name: str,
        callsite: str,
        attempt_num: int,
        max_attempts: int,
        elapsed_seconds: float,
        sleep_seconds: float,
        error_type: str,
        error_message: Optional[str],
        batch_num: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        _ = meta
        self.retry_events.append(
            {
                "loader_name": loader_name,
                "callsite": callsite,
                "attempt_num": attempt_num,
                "max_attempts": max_attempts,
                "elapsed_seconds": elapsed_seconds,
                "sleep_seconds": sleep_seconds,
                "error_type": error_type,
                "error_message": error_message,
                "batch_num": batch_num,
            }
        )

    def emit_error(self, error: Exception, context: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        _ = meta
        self.error_events.append((error, context))


class _FakeClock(object):
    def __init__(self) -> None:
        self.now: float = 0.0
        self.sleep_calls: List[float] = []

    def monotonic(self) -> float:
        return float(self.now)

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(float(seconds))
        self.now += float(seconds)


def _always_retry(_exc: Exception, _ctx: LoaderRetryContext) -> bool:
    return True


def test_loader_retry_policy_next_sleep_seconds_exponential_jitter(monkeypatch) -> None:
    monkeypatch.setattr(lr.secrets, "randbits", lambda _n: 1 << 52)
    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_always_retry,
        backoff="exponential",
        base_delay_seconds=0.2,
        max_delay_seconds=1.0,
        jitter=True,
    )

    assert policy.next_sleep_seconds(attempt_num=1) == pytest.approx(0.1)
    assert policy.next_sleep_seconds(attempt_num=3) == pytest.approx(0.4)


def test_call_with_loader_retry_attempt_limit_is_enforced() -> None:
    inst = _CaptureInstrumentation()
    calls: List[int] = []

    def _call() -> int:
        calls.append(1)
        raise RuntimeError("boom")

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_always_retry,
        max_attempts=2,
        max_elapsed_seconds=10.0,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = call_with_loader_retry(call=_call, instrumentation=inst, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD)

    assert len(calls) == 2
    assert len(inst.retry_events) == 1
    assert inst.retry_events[0]["attempt_num"] == 1

    assert len(inst.error_events) == 1
    assert inst.error_events[0][1]["retry_reason"] == "max_attempts_exceeded"


def test_call_with_loader_retry_supports_none_instrumentation() -> None:
    calls: List[int] = []

    def _call() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_always_retry,
        max_attempts=2,
        max_elapsed_seconds=10.0,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = call_with_loader_retry(call=_call, instrumentation=None, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD)

    assert len(calls) == 2


def test_call_with_loader_retry_should_retry_false_does_not_retry() -> None:
    inst = _CaptureInstrumentation()
    calls: List[int] = []

    def _call() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    def _should_retry(_exc: Exception, _ctx: LoaderRetryContext) -> bool:
        return False

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_should_retry,
        max_attempts=5,
        max_elapsed_seconds=10.0,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = call_with_loader_retry(call=_call, instrumentation=inst, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD)

    assert len(calls) == 1
    assert inst.retry_events == []
    assert len(inst.error_events) == 1
    assert inst.error_events[0][1]["retry_reason"] == "should_retry_false"


def test_call_with_loader_retry_should_retry_raises_is_treated_as_false() -> None:
    inst = _CaptureInstrumentation()

    def _call() -> None:
        raise RuntimeError("boom")

    def _should_retry(_exc: Exception, _ctx: LoaderRetryContext) -> bool:
        raise ValueError("bad should_retry")

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_should_retry,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = call_with_loader_retry(call=_call, instrumentation=inst, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD)

    assert inst.retry_events == []
    assert len(inst.error_events) == 1
    assert inst.error_events[0][1]["retry_reason"] == "should_retry_false"


def test_call_with_loader_retry_max_elapsed_limit_is_enforced(monkeypatch) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(lr.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(lr.time, "sleep", clock.sleep)

    inst = _CaptureInstrumentation()
    calls: List[int] = []

    def _call() -> None:
        calls.append(1)
        raise RuntimeError("boom")

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_always_retry,
        max_attempts=5,
        max_elapsed_seconds=0.15,
        backoff="fixed",
        base_delay_seconds=0.1,
        max_delay_seconds=0.1,
        jitter=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = call_with_loader_retry(call=_call, instrumentation=inst, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD)

    assert len(calls) == 2
    assert clock.sleep_calls == [0.1]
    assert len(inst.retry_events) == 1
    assert len(inst.error_events) == 1
    assert inst.error_events[0][1]["retry_reason"] == "max_elapsed_exceeded"


def test_call_with_loader_retry_max_elapsed_limit_can_stop_before_sleep(monkeypatch) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(lr.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(lr.time, "sleep", clock.sleep)

    inst = _CaptureInstrumentation()
    calls: List[int] = []

    def _call() -> None:
        calls.append(1)
        clock.now += 0.2
        raise RuntimeError("boom")

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_always_retry,
        max_attempts=5,
        max_elapsed_seconds=0.1,
        backoff="fixed",
        base_delay_seconds=0.1,
        max_delay_seconds=0.1,
        jitter=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = call_with_loader_retry(call=_call, instrumentation=inst, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD)

    assert len(calls) == 1
    assert inst.retry_events == []
    assert len(inst.error_events) == 1
    assert inst.error_events[0][1]["retry_reason"] == "max_elapsed_exceeded"


def test_call_with_loader_retry_error_message_is_wants_gated() -> None:
    class _ExplodingStrError(Exception):
        def __str__(self) -> str:
            raise AssertionError("str(exc) should not be called")

    inst = _CaptureInstrumentation(wants_retry=False)
    call_count = {"n": 0}

    def _call() -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise _ExplodingStrError()
        return "ok"

    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_always_retry,
        max_attempts=3,
        max_elapsed_seconds=10.0,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )

    assert call_with_loader_retry(call=_call, instrumentation=inst, policy=policy, loader_name="demo", callsite=CALLSITE_LOAD) == "ok"
    assert call_count["n"] == 2
    assert inst.retry_events == []
