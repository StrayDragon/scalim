from typing import TYPE_CHECKING, Tuple

from .loadref_scheduler import resolve_adaptive_max_workers
from .policy import DefaultAdaptivePolicy
from .tuning import AdaptiveTuning

if TYPE_CHECKING:
    from ..executor.runtime.runtime import ExecutionRuntime
    from ..pipeline.overrides import PipelineOverrides
    from .policy import AdaptivePolicy


def resolve_adaptive_policy_tuning_and_workers(
    *,
    runtime: "ExecutionRuntime",
    overrides: "PipelineOverrides",
) -> Tuple["AdaptivePolicy", AdaptiveTuning, int]:
    """解析自适应执行所需的(`policy`、`tuning`、`resolved_max_workers`).

    该辅助函数用于避免在解析/校验自适应配置时,流水线与批执行器之间出现语义漂移.
    """
    policy = overrides.adaptive_policy or DefaultAdaptivePolicy()
    tuning = overrides.adaptive_tuning
    if tuning is None:
        tuning = AdaptiveTuning(min_parallel_tasks_per_layer=int(overrides.adaptive_min_parallel_tasks or 2))
    tuning = policy.resolve_tuning(tuning)
    tuning.validate()

    max_workers_hint = int(tuning.max_workers) if int(tuning.max_workers) > 0 else int(runtime.max_workers)
    resolved_workers = resolve_adaptive_max_workers(max_workers_hint)
    return policy, tuning, resolved_workers


__all__ = [
    "resolve_adaptive_policy_tuning_and_workers",
]
