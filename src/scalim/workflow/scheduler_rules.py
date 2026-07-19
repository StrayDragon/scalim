"""工作流运行调度的纯谓词(不读取 `WorkflowRunController` 或线程池等执行器状态)."""

from ..typedefs import FailurePolicy, RuntimeValue


def should_cancel_on_failure(failure_policy: str, failed_outcome: RuntimeValue) -> bool:
    return (failure_policy or "") == FailurePolicy.ALL_FAIL and failed_outcome is not None


def can_schedule_more(submitted_count: int, max_concurrency: int) -> bool:
    return int(submitted_count) < int(max_concurrency)


__all__ = ()
