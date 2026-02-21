# region imports

from collections.abc import Sequence
from dataclasses import dataclass

from ...planning.operators import LoadRefOperatorIr
from ...planning.plan import ExecutionPlan
from ..executor.runtime.runtime import ExecutionRuntime
from .tuning import DEFAULT_ADAPTIVE_POOL, AdaptiveTuning

# endregion

ADAPTIVE_BACKEND_THREAD = "thread"
ADAPTIVE_BACKEND_PROCESS = "process"
ADAPTIVE_BACKEND_ASYNC = "async"

PROCESS_FAILURE_FAIL_FAST = "fail_fast"
PROCESS_FAILURE_FALLBACK_SERIAL = "fallback_to_serial"


@dataclass(frozen=True)
class AdaptiveLayerDecision:
    should_parallelize: bool
    reason: str | None = None


class AdaptivePolicy:
    """Adaptive scheduling policy.

    Users MAY subclass this type and override the decision methods to customize:
    - layer/task parallelism
    - task pool selection
    - backend selection (thread/process/async)

    When both `AdaptiveTuning` and `AdaptivePolicy` are provided, policy decisions take precedence; tuning is treated as defaults.
    """

    def resolve_tuning(self, tuning: AdaptiveTuning) -> AdaptiveTuning:
        return tuning

    def choose_backend(self, *, plan: ExecutionPlan, runtime: ExecutionRuntime, tuning: AdaptiveTuning) -> str:
        _ = plan
        _ = runtime
        _ = tuning
        return ADAPTIVE_BACKEND_THREAD

    def choose_process_failure_mode(self, *, plan: ExecutionPlan, runtime: ExecutionRuntime, tuning: AdaptiveTuning) -> str:
        _ = plan
        _ = runtime
        _ = tuning
        return PROCESS_FAILURE_FAIL_FAST

    def choose_task_pool(self, *, op: LoadRefOperatorIr, tuning: AdaptiveTuning) -> str:
        pools: set[str] = set()
        for step in op.lookup_steps:
            pools.add(tuning.pool_for_source(step.to_source.source_id))
        if len(pools) == 1:
            return next(iter(pools))
        # Multi-source chains default to the default pool to keep "one pool per task" and avoid multi-token deadlocks.
        return DEFAULT_ADAPTIVE_POOL

    def decide_layer_parallelism(
        self,
        layer_ops: Sequence[LoadRefOperatorIr],
        *,
        tuning: AdaptiveTuning,
        runtime: ExecutionRuntime,
        pool_is_available: bool,
        resolved_max_workers: int,
        layer_lookup_keys: dict[str, int] | None,
    ) -> AdaptiveLayerDecision:
        _ = runtime
        if not pool_is_available:
            return AdaptiveLayerDecision(should_parallelize=False, reason="no_pool")
        if int(resolved_max_workers) <= 1:
            return AdaptiveLayerDecision(should_parallelize=False, reason="single_worker")

        min_tasks = tuning.effective_min_parallel_tasks_per_layer()
        if len(layer_ops) < min_tasks:
            return AdaptiveLayerDecision(should_parallelize=False, reason="below_min_parallel_tasks")

        if layer_lookup_keys:
            total_keys = sum(int(v) for v in layer_lookup_keys.values())
            if int(tuning.min_total_lookup_keys_per_layer or 0) > 0 and total_keys < int(tuning.min_total_lookup_keys_per_layer):
                return AdaptiveLayerDecision(should_parallelize=False, reason="below_min_total_lookup_keys")

            if int(tuning.min_lookup_keys_per_task or 0) > 0:
                min_keys = int(tuning.min_lookup_keys_per_task)
                if any(int(v) < min_keys for v in layer_lookup_keys.values()):
                    return AdaptiveLayerDecision(should_parallelize=False, reason="below_min_lookup_keys_per_task")

        return AdaptiveLayerDecision(should_parallelize=True, reason=None)


class DefaultAdaptivePolicy(AdaptivePolicy):
    """Default policy: thread backend + tuning-based thresholds."""


__all__ = [
    "ADAPTIVE_BACKEND_ASYNC",
    "ADAPTIVE_BACKEND_PROCESS",
    "ADAPTIVE_BACKEND_THREAD",
    "PROCESS_FAILURE_FAIL_FAST",
    "PROCESS_FAILURE_FALLBACK_SERIAL",
    "AdaptiveLayerDecision",
    "AdaptivePolicy",
    "DefaultAdaptivePolicy",
]
