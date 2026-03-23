import asyncio
import logging
import threading

import pytest

from scalim.execution.adaptive.thread_loop_executor import (
    THREAD_LOOP_EXECUTOR_NON_CORO_TASK_WARNING,
    ThreadLoopExecutor,
    _best_effort_all_tasks,
)

_TIMEOUT_S = 5.0


def test_thread_loop_executor_runs_sync_and_coroutine_and_shutdown(caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.WARNING, logger="scalim.execution.adaptive.thread_loop_executor")

    executor = ThreadLoopExecutor(max_workers=2)
    try:
        fut = executor.submit(lambda: 1)  # noqa: E731
        assert fut.result(timeout=_TIMEOUT_S) == 1

        async def _coro() -> int:
            return 2

        fut = executor.submit(lambda: _coro())  # noqa: E731
        assert fut.result(timeout=_TIMEOUT_S) == 2
    finally:
        executor.shutdown(wait=True)

    warning_messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert warning_messages.count(THREAD_LOOP_EXECUTOR_NON_CORO_TASK_WARNING) == 1

    with pytest.raises(RuntimeError, match="shutdown"):
        _ = executor.submit(lambda: 3)  # noqa: E731


def test_thread_loop_executor_shutdown_cancels_pending_tasks_and_is_idempotent() -> None:
    executor = ThreadLoopExecutor(max_workers=1)
    started = threading.Event()
    fut = None
    try:

        async def _block() -> None:
            started.set()
            await asyncio.Event().wait()

        fut = executor.submit(lambda: _block())  # noqa: E731
        assert started.wait(timeout=_TIMEOUT_S)
    finally:
        executor.shutdown(wait=True)

    executor.shutdown(wait=True)

    assert fut is not None
    with pytest.raises(Exception):  # noqa: BLE001
        _ = fut.result(timeout=_TIMEOUT_S)


def test_best_effort_all_tasks_falls_back_to_legacy_task_all_tasks() -> None:
    loop = asyncio.new_event_loop()
    try:

        class _DummyTask:
            @staticmethod
            def all_tasks(*, loop):  # type: ignore[no-untyped-def]
                _ = loop
                return {object()}

        class _AsyncioCompatModule:
            all_tasks = None
            Task = _DummyTask

        pending = _best_effort_all_tasks(loop, asyncio_module=_AsyncioCompatModule())
        assert len(pending) == 1
    finally:
        loop.close()
