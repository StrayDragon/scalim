# region imports

from dataclasses import dataclass, field

# endregion

DEFAULT_ADAPTIVE_POOL = "default"


@dataclass(frozen=True)
class AdaptiveTuning:
    """Tuning knobs for `parallel_mode="adaptive"`.

    This object is intentionally DSL-agnostic: it is injected via Python/IR entrypoints (e.g. `PipelineOverrides`).
    """

    # Global concurrency cap for the adaptive executor.
    # - 0/negative means "auto" (aligned with `ScalimEngine(max_workers=0)` semantics).
    max_workers: int = 0

    # Resource pools: pool_name -> concurrency limit (MUST be >= 1).
    pools: dict[str, int] = field(default_factory=dict)

    # Source binding: source_id -> pool_name. Unmapped sources fall back to DEFAULT_ADAPTIVE_POOL.
    source_pools: dict[str, str] = field(default_factory=dict)

    # Thresholds to avoid parallel overhead for tiny workloads.
    # Note: parallelizing a layer with <2 tasks is never useful; the scheduler clamps this accordingly.
    min_parallel_tasks_per_layer: int = 2

    # If >0, total first-step lookup key count per layer below this threshold will run serially.
    min_total_lookup_keys_per_layer: int = 0

    # If >0, any task whose first-step lookup key count is below this threshold will run serially.
    min_lookup_keys_per_task: int = 0

    def validate(self) -> None:
        self._validate_pools()
        self._validate_source_pools()
        self._validate_thresholds()

    def _validate_pools(self) -> None:
        for pool_name, limit in self.pools.items():
            if not pool_name:
                msg = "AdaptiveTuning.pools keys must be non-empty"
                raise ValueError(msg)
            if int(limit) < 1:
                msg = f"AdaptiveTuning.pools['{pool_name}'] must be >= 1"
                raise ValueError(msg)

    def _validate_source_pools(self) -> None:
        for source_id, pool_name in self.source_pools.items():
            if not source_id:
                msg = "AdaptiveTuning.source_pools keys must be non-empty"
                raise ValueError(msg)
            if not pool_name:
                msg = f"AdaptiveTuning.source_pools['{source_id}'] must be non-empty"
                raise ValueError(msg)
            if pool_name != DEFAULT_ADAPTIVE_POOL and pool_name not in self.pools:
                msg = f"AdaptiveTuning.source_pools['{source_id}'] refers to unknown pool '{pool_name}'"
                raise ValueError(msg)

    def _validate_thresholds(self) -> None:
        if int(self.min_parallel_tasks_per_layer) < 1:
            msg = "AdaptiveTuning.min_parallel_tasks_per_layer must be >= 1"
            raise ValueError(msg)
        if int(self.min_total_lookup_keys_per_layer) < 0:
            msg = "AdaptiveTuning.min_total_lookup_keys_per_layer must be >= 0"
            raise ValueError(msg)
        if int(self.min_lookup_keys_per_task) < 0:
            msg = "AdaptiveTuning.min_lookup_keys_per_task must be >= 0"
            raise ValueError(msg)

    def pool_for_source(self, source_id: str) -> str:
        return self.source_pools.get(source_id, DEFAULT_ADAPTIVE_POOL)

    def resolve_pool_limit(self, pool_name: str, *, resolved_max_workers: int) -> int:
        if pool_name in self.pools:
            return max(1, int(self.pools[pool_name]))
        if pool_name == DEFAULT_ADAPTIVE_POOL:
            # Default pool limit is implementation-defined when absent; we align it with global concurrency.
            return max(1, int(resolved_max_workers))
        # Unknown pool names should be prevented by validation; fall back defensively.
        return max(1, int(resolved_max_workers))

    def effective_min_parallel_tasks_per_layer(self) -> int:
        # Parallelizing a layer with <2 tasks is meaningless; clamp for safety and determinism.
        return max(2, int(self.min_parallel_tasks_per_layer or 2))


__all__ = [
    "DEFAULT_ADAPTIVE_POOL",
    "AdaptiveTuning",
]
