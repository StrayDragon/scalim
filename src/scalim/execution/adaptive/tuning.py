# region imports

from dataclasses import dataclass, field

# endregion

DEFAULT_ADAPTIVE_POOL = "default"


@dataclass(frozen=True)
class AdaptiveTuning:
    """`parallel_mode=\"adaptive\"` 的调优参数.

    该对象刻意保持 DSL 无关: 通过 Python/IR 入口注入 (例如 `PipelineOverrides`).
    """

    # 自适应执行器的全局并发上限.
    # - 0/负数表示自动 (与 `ScalimEngine(max_workers=0)` 语义对齐).
    max_workers: int = 0

    # 资源池: pool_name -> 并发上限 (必须 >= 1).
    pools: dict[str, int] = field(default_factory=dict)

    # 数据源绑定: source_id -> pool_name. 未映射的数据源回退到 DEFAULT_ADAPTIVE_POOL.
    source_pools: dict[str, str] = field(default_factory=dict)

    # 阈值: 用于避免小工作量时的并发开销.
    # 注意: 对 <2 个任务的层做并发没有意义; 调度器会据此进行限制.
    min_parallel_tasks_per_layer: int = 2

    # 若 >0: 当某层的“第一步查找键总数”低于该阈值时,该层串行执行.
    min_total_lookup_keys_per_layer: int = 0

    # 若 >0: 当某个任务的“第一步查找键数量”低于该阈值时,该任务串行执行.
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
            # 未配置默认池上限时,其行为依赖具体实现;这里将其对齐到全局并发上限.
            return max(1, int(resolved_max_workers))
        # 未知池名应由校验提前阻止;这里做防御性回退.
        return max(1, int(resolved_max_workers))

    def effective_min_parallel_tasks_per_layer(self) -> int:
        # 对 <2 个任务的层做并发没有意义;为安全与确定性进行限制.
        return max(2, int(self.min_parallel_tasks_per_layer or 2))


__all__ = [
    "DEFAULT_ADAPTIVE_POOL",
    "AdaptiveTuning",
]
