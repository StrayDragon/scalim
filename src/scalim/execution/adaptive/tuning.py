# region imports

from typing import Dict

from ...vendor.dataclassesx import dataclass, field

# endregion

DEFAULT_ADAPTIVE_POOL = "default"


@dataclass(frozen=True)
class AdaptiveTuning:
    """`parallel_mode=\"adaptive\"` 的调参项.

    此对象刻意与 `DSL` 无关:通过 `Python`/`IR` 入口(例如 `PipelineOverrides`)注入.
    """

    # 自适应执行器的全局并发上限.
    # - 0/负数表示“自动”(与 `ScalimEngine(max_workers=0)` 语义对齐).
    max_workers: int = 0

    # 资源池:`pool_name` -> 并发上限(必须 >= 1).
    pools: Dict[str, int] = field(default_factory=dict)

    # 数据源绑定:`source_id` -> `pool_name`.未映射的数据源回退到 `DEFAULT_ADAPTIVE_POOL`.
    source_pools: Dict[str, str] = field(default_factory=dict)

    # 阈值:避免在极小工作负载上产生并行开销.
    # 注意:对少于 2 个任务的层做并行没有意义;调度器会据此做下限收敛.
    min_parallel_tasks_per_layer: int = 2

    # 若 >0,则当每层首步查找键总数低于该阈值时,按串行执行.
    min_total_lookup_keys_per_layer: int = 0

    # 若 >0,则当任一任务的首步查找键数量低于该阈值时,按串行执行.
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
                msg = "AdaptiveTuning.pools['{}'] must be >= 1".format(pool_name)
                raise ValueError(msg)

    def _validate_source_pools(self) -> None:
        for source_id, pool_name in self.source_pools.items():
            if not source_id:
                msg = "AdaptiveTuning.source_pools keys must be non-empty"
                raise ValueError(msg)
            if not pool_name:
                msg = "AdaptiveTuning.source_pools['{}'] must be non-empty".format(source_id)
                raise ValueError(msg)
            if pool_name != DEFAULT_ADAPTIVE_POOL and pool_name not in self.pools:
                msg = "AdaptiveTuning.source_pools['{}'] refers to unknown pool '{}'".format(source_id, pool_name)
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
            # 若未显式配置默认池上限,则实现可自行决定;这里将其与全局并发对齐.
            return max(1, int(resolved_max_workers))
        # 未知的资源池名称应由校验阻止;此处仍做防御性回退.
        return max(1, int(resolved_max_workers))

    def effective_min_parallel_tasks_per_layer(self) -> int:
        # 对少于 2 个任务的层做并行没有意义;为安全性与确定性做下限收敛.
        return max(2, int(self.min_parallel_tasks_per_layer or 2))


__all__ = [
    "DEFAULT_ADAPTIVE_POOL",
    "AdaptiveTuning",
]
