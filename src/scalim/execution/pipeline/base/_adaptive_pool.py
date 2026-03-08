from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import ExitStack
from typing import Optional
from warnings import warn

from ....planning.plan import ExecutionPlan
from ...adaptive.config import resolve_adaptive_policy_tuning_and_workers
from ...adaptive.policy import ADAPTIVE_BACKEND_ASYNC, ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_THREAD
from ...adaptive.thread_loop_executor import ThreadLoopExecutor
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

    _ = warnings_module
    backend = policy.choose_backend(plan=plan, runtime=runtime, tuning=tuning)
    if backend == ADAPTIVE_BACKEND_PROCESS:
        warn(
            "检测到 parallel_mode='adaptive' 且 backend='process':该实现仍不成熟/实验性,可能不稳定;建议优先使用 backend='thread'.",
            RuntimeWarning,
            stacklevel=2,
        )  # pragma: no cover
    elif backend == ADAPTIVE_BACKEND_ASYNC:
        version_info = getattr(sys_module, "version_info", None)
        is_py36 = version_info is not None and tuple(version_info) < (3, 7)
        if is_py36:
            warn(
                "检测到 parallel_mode='adaptive' 且 backend='async':该实现仍不成熟,且在 Python 3.6 下不支持;将回退到 backend='thread'.",
                RuntimeWarning,
                stacklevel=2,
            )  # pragma: no cover
            backend = ADAPTIVE_BACKEND_THREAD
        else:
            warn(
                "检测到 parallel_mode='adaptive' 且 backend='async':该实现仍不成熟(Python 3.6 更不成熟);建议优先使用 backend='thread'.",
                RuntimeWarning,
                stacklevel=2,
            )  # pragma: no cover

    runtime.adaptive_backend = backend
    runtime.adaptive_process_failure_mode = None
    if backend == ADAPTIVE_BACKEND_PROCESS:
        runtime.adaptive_process_failure_mode = policy.choose_process_failure_mode(plan=plan, runtime=runtime, tuning=tuning)

    executor_cls = overrides.adaptive_executor_cls or ThreadPoolExecutor
    if backend == ADAPTIVE_BACKEND_THREAD:
        executor_cls = overrides.adaptive_executor_cls or ThreadPoolExecutor
    elif backend == ADAPTIVE_BACKEND_PROCESS:
        executor_cls = overrides.adaptive_process_executor_cls or ProcessPoolExecutor
    elif backend == ADAPTIVE_BACKEND_ASYNC:
        executor_cls = overrides.adaptive_async_executor_cls or ThreadLoopExecutor
    else:
        msg = "Invalid adaptive backend '{}'".format(backend)
        raise ValueError(msg)

    return stack.enter_context(executor_cls(max_workers=resolved_workers))


__all__ = [
    "maybe_create_adaptive_pool",
]
