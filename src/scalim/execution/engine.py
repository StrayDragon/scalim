# region imports

import threading
from typing import TYPE_CHECKING, Iterable, MutableMapping, Optional, Sequence

from ..hooks import HookManager
from ..ob.manager import ObserverManager
from ..planning.plan import ExecutionPlan
from ..sinks import ISink
from ..spec.ir import DemandIr
from ..typedefs import KeyNormalizationMode, LoaderResultMapping, RowData
from .executor.batch.executor import BatchExecutor
from .executor.runtime.runtime import ExecutionRuntime
from .guardrails import GuardrailsPolicy
from .loader_retry import LoaderRetryPolicies
from .pipeline.base.pipeline import Pipeline, SeqPipeline
from .pipeline.overrides import PipelineOverrides

# endregion

if TYPE_CHECKING:
    from .workflow_cache_pool import WorkflowCachePool


class ScalimEngine:
    """计算引擎.

    处理链路:`plan` -> `pipeline`(`executor`)-> `sink`.
    """

    demand: DemandIr
    plan: ExecutionPlan
    hook_manager: HookManager
    observer_manager: ObserverManager
    batch_size: Optional[int]
    gc_interval: int
    _pipeline: Pipeline
    _run_lock: "threading.RLock"

    def __init__(
        self,
        demand: DemandIr,
        plan: ExecutionPlan,
        hook_manager: Optional[HookManager] = None,
        observer_manager: Optional[ObserverManager] = None,
        batch_size: Optional[int] = 1000,
        gc_interval: int = 10,
        parallel_mode: str = "seq",
        max_workers: int = 0,
        key_normalization: KeyNormalizationMode = "raw",
        pipeline_overrides: Optional[PipelineOverrides] = None,
        guardrails: Optional[GuardrailsPolicy] = None,
        loader_retry: Optional[LoaderRetryPolicies] = None,
        preloaded_cache: Optional[MutableMapping[str, LoaderResultMapping]] = None,
        workflow_cache_pool: Optional["WorkflowCachePool"] = None,
        workflow_node_id: Optional[str] = None,
    ) -> None:
        """初始化 `ScalimEngine` 计算引擎.

        参数:
            `demand`: 统计需求数据结构
            `plan`: 执行计划
            `hook_manager`: 可选的钩子管理器,用于流程定制
            `observer_manager`: 可选的观测管理器,用于事件监听
            `batch_size`: 每个批次的记录数(`None` 表示不分批)
            `gc_interval`: 每隔 `N` 个批次运行一次 `GC`
            `parallel_mode`: 执行模式(`seq`:顺序;`adaptive`:自适应并发)
            `max_workers`: `adaptive` 并发上限(`0` 表示自动;`seq` 下忽略)
            `pipeline_overrides`: 可选的 `pipeline` 扩展点覆盖对象
            `guardrails`: 可选的防护策略
            `loader_retry`: 可选的加载重试策略
        """
        self.demand = demand
        self.plan = plan
        self.hook_manager = hook_manager or HookManager()
        self.observer_manager = observer_manager or ObserverManager()
        if batch_size is None:
            resolved_batch_size = None
        elif isinstance(batch_size, bool) or not isinstance(batch_size, int):
            msg = "Invalid batch_size={!r}. Expected null or an integer >= 1.".format(batch_size)
            raise TypeError(msg)
        elif batch_size < 1:
            msg = "Invalid batch_size={!r}. Expected null or an integer >= 1.".format(batch_size)
            raise ValueError(msg)
        else:
            resolved_batch_size = batch_size
        self.batch_size = resolved_batch_size
        self.gc_interval = gc_interval
        self._run_lock = threading.RLock()

        if parallel_mode in ("thread", "process"):
            msg = (
                "parallel_mode='{}' was removed. "
                "Use parallel_mode='adaptive' (auto fan-out/fan-in for intrabatch LoadRef) or parallel_mode='seq'."
            ).format(parallel_mode)
            raise ValueError(msg)
        if parallel_mode not in ("seq", "adaptive"):
            msg = "Invalid parallel_mode='{}'. Expected 'seq' or 'adaptive'.".format(parallel_mode)
            raise ValueError(msg)

        runtime = ExecutionRuntime(
            plan=plan,
            hook_manager=self.hook_manager,
            observer_manager=self.observer_manager,
            main_source=self.demand.main_source,
            guardrails=guardrails,
            loader_retry=loader_retry,
            parallel_mode=parallel_mode,
            max_workers=max_workers,
            key_normalization=key_normalization,
            preloaded_cache=preloaded_cache,
            workflow_cache_pool=workflow_cache_pool,
            workflow_node_id=workflow_node_id,
        )
        executor = BatchExecutor(plan, runtime, overrides=pipeline_overrides)

        self._pipeline = SeqPipeline(
            plan=plan,
            executor=executor,
            runtime=runtime,
            hook_manager=self.hook_manager,
            observer_manager=self.observer_manager,
            demand=demand,
            batch_size=resolved_batch_size,
            gc_interval=gc_interval,
            overrides=pipeline_overrides,
        )

    def run(
        self,
        main_rows: Optional[Iterable[RowData]] = None,
        sink: Optional[ISink] = None,
    ) -> Sequence[RowData]:
        """执行流水线.

        参数:
            `main_rows`: 可选的主数据行流;如果不提供则从主数据源加载
            `sink`: 可选的输出 `sink`

        返回:
            结果行列表(如果提供了 `sink` 则返回空列表)
        """
        with self._run_lock:
            return self._pipeline.run(main_rows, sink)


__all__ = ()
