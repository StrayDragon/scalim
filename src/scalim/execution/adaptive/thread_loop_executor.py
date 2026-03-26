# region imports

import asyncio
import contextlib
import logging
import threading
from concurrent.futures import Executor, Future
from typing import Any, Callable, Optional, Set, cast

from ..._internal.loggingx import prefix
from ...vendor.compact.typing_extensionsx import override

# endregion


def _best_effort_all_tasks(loop: "asyncio.AbstractEventLoop", asyncio_module: Any = asyncio) -> "Set[Any]":
    try:
        all_tasks = asyncio_module.all_tasks
    except AttributeError:  # pragma: no cover
        all_tasks = None
    if all_tasks is not None:
        try:
            return all_tasks(loop=loop)  # type: ignore[call-arg]
        except TypeError:  # pragma: no cover
            return all_tasks(loop)  # type: ignore[call-arg]

    try:
        task_cls = asyncio_module.Task
    except AttributeError:  # pragma: no cover
        task_cls = None
    if task_cls is None:  # pragma: no cover
        return set()
    try:
        legacy_all_tasks = task_cls.all_tasks
    except AttributeError:  # pragma: no cover
        legacy_all_tasks = None
    if legacy_all_tasks is None:  # pragma: no cover
        return set()
    try:
        return legacy_all_tasks(loop=loop)  # type: ignore[call-arg]
    except TypeError:  # pragma: no cover
        return legacy_all_tasks(loop)  # type: ignore[call-arg]


_logger = logging.getLogger(__name__)

THREAD_LOOP_EXECUTOR_NON_CORO_TASK_WARNING = (
    prefix("adaptive") + "`ThreadLoopExecutor` 收到非协程任务; 将在事件循环线程执行,可能阻塞. 请将任务改为协程,或改用线程/进程执行."
)


class ThreadLoopExecutor(Executor):
    """异步后端适配器:在独立线程托管的事件循环上运行可等待对象.

    语义:
    - 如果 `fn(*args, **kwargs)` 返回协程,则在该事件循环上 `await`.
    - 如果返回非协程,则在事件循环线程中直接执行(可能阻塞事件循环).
    - 并发度通过 `asyncio` 信号量按 `max_workers` 限制.

    该执行器为实验性功能,需要通过 `AdaptivePolicy.choose_backend()` 显式启用.
    """

    _max_workers: int
    _loop: "asyncio.AbstractEventLoop"
    _thread: threading.Thread
    _shutdown: bool
    _sem: Optional["asyncio.Semaphore"]
    _warned_sync_submit: bool
    _submit_lock: threading.Lock

    def __init__(self, max_workers: int = 1) -> None:
        super().__init__()
        self._max_workers = max(1, int(max_workers or 1))
        self._loop = asyncio.new_event_loop()
        self._shutdown = False
        self._sem = None
        self._warned_sync_submit = False
        self._submit_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run_loop, name="scalim-adaptive-async", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._sem = asyncio.Semaphore(self._max_workers)
        self._loop.run_forever()

        # 尽力清理(保持与 `Python 3.6` 兼容).
        pending = _best_effort_all_tasks(self._loop)
        for task in pending:
            task.cancel()
        with contextlib.suppress(Exception):
            _ = self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.close()

    @override
    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> "Future[Any]":  # type: ignore[override]
        with self._submit_lock:
            if self._shutdown:
                msg = "ThreadLoopExecutor is shutdown"
                raise RuntimeError(msg)

            async def _call() -> Any:
                sem = self._sem
                if sem is None:  # pragma: no cover
                    sem = asyncio.Semaphore(self._max_workers)
                    self._sem = sem
                async with sem:
                    result = fn(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        return await result
                    if not self._warned_sync_submit:
                        self._warned_sync_submit = True
                        _logger.warning(THREAD_LOOP_EXECUTOR_NON_CORO_TASK_WARNING)
                    return result

            return asyncio.run_coroutine_threadsafe(_call(), self._loop)

    @override
    def shutdown(self, wait: bool = True, **_kwargs: Any) -> None:  # type: ignore[override]  # noqa: FBT001, FBT002
        with self._submit_lock:
            if self._shutdown:
                return
            self._shutdown = True
        _ = cast("Any", self._loop).call_soon_threadsafe(self._loop.stop)
        if wait:
            self._thread.join(timeout=5.0)


__all__ = ["ThreadLoopExecutor"]
