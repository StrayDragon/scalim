from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import ExitStack
from types import TracebackType
from typing import Optional, Type

from ....planning.plan import ExecutionPlan
from ...adaptive.config import resolve_adaptive_policy_tuning_and_workers
from ...adaptive.policy import ADAPTIVE_BACKEND_ASYNC, ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_THREAD
from ...executor.runtime.runtime import ExecutionRuntime
from ..overrides import PipelineOverrides


def maybe_create_adaptive_pool(
    *,
    plan: ExecutionPlan,
    runtime: ExecutionRuntime,
    overrides: PipelineOverrides,
    stack: ExitStack,
    sys_module: object,
    warnings_module: object,
) -> Optional[Executor]:
    if runtime.parallel_mode != "adaptive":
        return None

    policy, tuning, resolved_workers = resolve_adaptive_policy_tuning_and_workers(runtime=runtime, overrides=overrides)
    if resolved_workers <= 1:
        return None

    _ = sys_module
    _ = warnings_module
    backend = policy.choose_backend(plan=plan, runtime=runtime, tuning=tuning)

    if backend in (ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_ASYNC):
        # `NOTE`: 若需回加 `process`/`async` 后端,请恢复对应实现模块与测试.
        msg = "adaptive backend '{}' 暂不支持: 当前仅支持 thread;请将 backend 改为 'thread'".format(backend)
        raise ValueError(msg)

    runtime.adaptive_backend = backend
    runtime.adaptive_process_failure_mode = None

    if backend == ADAPTIVE_BACKEND_THREAD:
        executor_cls = overrides.adaptive_executor_cls or ThreadPoolExecutor
    else:
        msg = "Invalid adaptive backend '{}'".format(backend)
        raise ValueError(msg)

    executor = executor_cls(max_workers=resolved_workers)

    def _shutdown_executor(
        exc_type: Optional[Type[BaseException]],
        _exc: Optional[BaseException],
        _tb: Optional[TracebackType],
    ) -> bool:
        # 说明:
        # - 正常路径: `wait=True` 保障线程池资源收敛.
        # - 异常路径: `wait=False` 避免在“卡死任务”场景下 `shutdown(wait=True)` 无限等待.
        #   注意: `Python` 线程无法安全强杀,因此 `wait=False` 仅用于快速失败(`fail-fast`);后台线程可能继续运行一段时间.
        executor.shutdown(wait=exc_type is None)
        return False

    _ = stack.push(_shutdown_executor)
    return executor


__all__ = ()
