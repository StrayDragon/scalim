from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import ExitStack

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
) -> Executor | None:
    if runtime.parallel_mode != "adaptive":
        return None

    policy, tuning, resolved_workers = resolve_adaptive_policy_tuning_and_workers(runtime=runtime, overrides=overrides)
    if resolved_workers <= 1:
        return None

    backend = policy.choose_backend(plan=plan, runtime=runtime, tuning=tuning)
    if backend == ADAPTIVE_BACKEND_THREAD:
        executor_cls = overrides.adaptive_executor_cls or ThreadPoolExecutor
    elif backend == ADAPTIVE_BACKEND_PROCESS:
        from concurrent.futures import ProcessPoolExecutor  # noqa: PLC0415

        executor_cls = overrides.adaptive_process_executor_cls or ProcessPoolExecutor
    elif backend == ADAPTIVE_BACKEND_ASYNC:
        from ...adaptive.thread_loop_executor import ThreadLoopExecutor  # noqa: PLC0415

        executor_cls = overrides.adaptive_async_executor_cls or ThreadLoopExecutor
    else:
        msg = f"Invalid adaptive backend '{backend}'"
        raise ValueError(msg)

    return stack.enter_context(executor_cls(max_workers=resolved_workers))


__all__ = [
    "maybe_create_adaptive_pool",
]
