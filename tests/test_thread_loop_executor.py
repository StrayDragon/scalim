import asyncio
import logging
import threading

import pytest

from scalim.execution.adaptive.thread_loop_executor import ThreadLoopExecutor, _best_effort_all_tasks


def test_thread_loop_executor_runs_sync_and_coroutine_and_shutdown(caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.WARNING, logger="scalim.execution.adaptive.thread_loop_executor")

    executor = ThreadLoopExecutor(max_workers=2)
    try:
        fut = executor.submit(lambda: 1)  # noqa: E731
        assert fut.result(timeout=1.0) == 1

        async def _coro() -> int:
            return 2

        fut = executor.submit(lambda: _coro())  # noqa: E731
        assert fut.result(timeout=1.0) == 2
    finally:
        executor.shutdown(wait=True)

    warning_messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]
    assert len([msg for msg in warning_messages if "non-coroutine task" in msg]) == 1

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
        assert started.wait(timeout=1.0)
    finally:
        executor.shutdown(wait=True)

    executor.shutdown(wait=True)

    assert fut is not None
    with pytest.raises(Exception):  # noqa: BLE001
        _ = fut.result(timeout=1.0)


def test_best_effort_all_tasks_falls_back_to_legacy_task_all_tasks(monkeypatch) -> None:
    loop = asyncio.new_event_loop()
    try:
        monkeypatch.setattr(asyncio, "all_tasks", None, raising=False)

        class _DummyTask:
            @staticmethod
            def all_tasks(*, loop):  # type: ignore[no-untyped-def]
                _ = loop
                return {object()}

        monkeypatch.setattr(asyncio, "Task", _DummyTask, raising=True)
        pending = _best_effort_all_tasks(loop)
        assert len(pending) == 1
    finally:
        loop.close()
