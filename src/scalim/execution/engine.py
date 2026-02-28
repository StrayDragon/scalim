# region imports

from collections.abc import Iterable, Sequence

from ..hooks.base import HookManager
from ..ob.manager import ObserverManager
from ..planning.plan import ExecutionPlan
from ..sinks.sink_base import ISink
from ..spec.ir.demand import DemandIr
from ..typedefs import RowData
from .executor.batch.executor import BatchExecutor
from .executor.runtime.runtime import ExecutionRuntime
from .guardrails import GuardrailsPolicy
from .loader_retry import LoaderRetryPolicies
from .pipeline.base.pipeline import Pipeline, SeqPipeline
from .pipeline.overrides import PipelineOverrides

# endregion


class ScalimEngine:
    """计算引擎

    执行链路: 执行计划 -> 流水线(执行器) -> 输出端
    """

    demand: DemandIr
    plan: ExecutionPlan
    hook_manager: HookManager
    observer_manager: ObserverManager
    batch_size: int
    gc_interval: int
    _pipeline: Pipeline

    def __init__(
        self,
        demand: DemandIr,
        plan: ExecutionPlan,
        hook_manager: HookManager | None = None,
        observer_manager: ObserverManager | None = None,
        batch_size: int = 1000,
        gc_interval: int = 10,
        parallel_mode: str = "seq",
        max_workers: int = 0,
        pipeline_overrides: PipelineOverrides | None = None,
        guardrails: GuardrailsPolicy | None = None,
        loader_retry: LoaderRetryPolicies | None = None,
    ) -> None:
        """初始化 Scalim 计算引擎

        参数：
            `demand`: 统计需求数据结构
            `plan`: 执行计划
            `hook_manager`: 可选的钩子管理器,用于流程定制
            `observer_manager`: 可选的观测管理器,用于事件监听
            `batch_size`: 每个批次的记录数
            `gc_interval`: 每隔 N 个批次运行 GC
            `parallel_mode`: 执行模式 (`seq`: 顺序, `adaptive`: 自适应并发)
            `max_workers`: `adaptive` 并发上限 (0 = 自动; `seq` 下忽略)
            `pipeline_overrides`: 可选的流水线扩展点覆盖对象
        """
        self.demand = demand
        self.plan = plan
        self.hook_manager = hook_manager or HookManager()
        self.observer_manager = observer_manager or ObserverManager()
        self.batch_size = batch_size
        self.gc_interval = gc_interval

        if parallel_mode in ("thread", "process"):
            msg = (
                f"parallel_mode='{parallel_mode}' was removed. "
                "Use parallel_mode='adaptive' (auto fan-out/fan-in for intrabatch LoadRef) or parallel_mode='seq'."
            )
            raise ValueError(msg)
        if parallel_mode not in ("seq", "adaptive"):
            msg = f"Invalid parallel_mode='{parallel_mode}'. Expected 'seq' or 'adaptive'."
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
        )
        executor = BatchExecutor(plan, runtime, overrides=pipeline_overrides)

        self._pipeline = SeqPipeline(
            plan=plan,
            executor=executor,
            runtime=runtime,
            hook_manager=self.hook_manager,
            observer_manager=self.observer_manager,
            demand=demand,
            batch_size=batch_size,
            gc_interval=gc_interval,
            overrides=pipeline_overrides,
        )

    def run(
        self,
        main_rows: Iterable[RowData] | None = None,
        sink: ISink | None = None,
    ) -> Sequence[RowData]:
        """执行流水线

        参数：
            `main_rows`: 可选的主数据行流,如果不提供则从主数据源加载
            `sink`: 可选的输出端(`sink`)

        返回：
            结果行列表 (如果提供了 `sink` 则返回空列表)
        """
        return self._pipeline.run(main_rows, sink)
