"""执行契约(`DSL` 无关).

说明:
- 本模块仅包含纯 `contracts`(数据结构),不包含执行编排逻辑.
- 运行时需兼容 `Python 3.6`.
"""

from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple, Union

from ..typedefs import KeyNormalizationMode, ParallelMode, RowData
from ..vendor.dataclassesx import dataclass
from ..vendor.dataclassesx import field as dataclass_field
from .output_contracts import ExportLayout, OutputSpec

if TYPE_CHECKING:
    from ..hooks import IExecutionHook
    from ..ob.observer import Observer
    from ..ob.presets.viz import VizObserverConfig
    from ..planning.plan import ExecutionPlan
    from ..sinks import InMemoryCsv, ISink
    from ..sinks.rows import InMemoryRows
    from ..spec.ir import DemandIr
    from .guardrails import GuardrailsPolicy
    from .loader_retry import LoaderRetryPolicies
    from .output_composition import OutputCompositionSpec, OutputTargetStats
    from .runtime_bindings import RuntimeBindings


@dataclass(frozen=True)
class ObservabilitySpec:
    """与 `DSL` 无关的可观测性请求(用于运行编排).

    - `viz_config` 可选;在构建执行计划后会物化为 `VizObserver`.
    """

    fallback_logger_enabled: bool = False
    viz_config: Optional["VizObserverConfig"] = None


@dataclass(frozen=True)
class ExecutionRequest:
    export_layout: ExportLayout
    """导出布局(字段顺序与可选表头)."""

    output: OutputSpec = dataclass_field(default_factory=OutputSpec)
    """输出策略(例如输出格式、路径、编码、是否流式)."""

    sink: Optional["ISink"] = None
    """可选:显式指定输出端;若为 `None` 则按 `output` 策略创建."""

    observability: Optional[ObservabilitySpec] = None
    """可选:可观测性请求(例如 `viz` 配置)."""

    components: Optional[List[Union["Observer", "IExecutionHook"]]] = None
    """可选:要挂载的 `Observer`/`Hook` 组件列表."""

    batch_size: Optional[int] = 1000
    """批大小(`None` 表示不分批)."""

    parallel_mode: ParallelMode = "seq"
    """并行模式(`seq` 或 `adaptive`)."""

    max_workers: int = 0
    """最大并发工作数提示(`0` 表示自动)."""

    key_normalization: KeyNormalizationMode = "raw"
    """可选: `key` 规范化模式(实验性;默认 `raw`)."""

    guardrails: Optional["GuardrailsPolicy"] = None
    """可选:运行时护栏策略."""

    loader_retry: Optional["LoaderRetryPolicies"] = None
    """可选:加载重试策略."""

    runtime_bindings: Optional["RuntimeBindings"] = None
    """可选:运行时绑定(`RuntimeBindings`).

    说明:
    - 静态 `IR`/`ExecutionPlan` 不得保存 `Python` 可调用对象;执行阶段所需函数对象通过 `RuntimeBindings` 注入(通常由“运行时链接”阶段产出).
    - 当为 `None` 时,执行阶段无法解析加载器、派生字段计算等运行时函数.
    """

    output_composition: Optional["OutputCompositionSpec"] = None
    """可选:多输出组合请求(`IR/Python-only`).

    当提供该字段时:
    - `output`/`sink` 的单输出装配将被忽略
    - 运行计划的目标字段将由组合请求的 `required_demand_fields` 计算得出
    """

    main_rows: Optional[Iterable[RowData]] = None
    """可选:显式注入 `main_rows`(当提供时绕过主数据源 `loader`)."""

    capture_in_memory_rows: bool = False
    """可选:捕获本次运行输出的 `InMemoryRows`(保留 `FieldValue` 类型域;默认关闭)."""


@dataclass(frozen=True)
class ExecutionResult:
    """与 `DSL` 无关的执行结果.

    注意:
    - `total_rows` 统计写入到实际输出端的行数(包括 `NullSink`),这是输出/写出的行数.
    - 可观测性指标可能使用不同口径来做低开销吞吐估算
      (例如 `PerformanceMetrics.total_rows` 统计的是输入 `row_ids`).
    """

    output_path: Optional[str]
    total_rows: int
    duration: float
    demand_ir: "DemandIr"
    plan: "ExecutionPlan"
    outputs: Optional[Dict[str, str]] = None
    """可选:输出目标到 `output_path` 的映射(多输出组合时提供)."""

    output_target_stats: Optional[List["OutputTargetStats"]] = None
    """可选:每个输出目标的统计(行数/耗时/错误/禁用)(多输出组合时提供)."""

    in_memory_csv_outputs: Optional[Dict[str, "InMemoryCsv"]] = None
    """可选: `workflow-managed` 输出的 CSV 工件映射(多输出组合时提供)."""

    in_memory_rows_outputs: Optional[Dict[str, "InMemoryRows"]] = None
    """可选: `workflow-managed` 输出的类型化行工件映射(多输出组合时提供)."""

    workflow_managed_output_export_headers: Optional[Dict[str, Tuple[str, ...]]] = None
    """可选: `xlsx_memory` 工作流托管输出的结果侧导出表头元数据."""

    in_memory_rows: Optional["InMemoryRows"] = None
    """可选: `workflow-intermediate-store` 的 `InMemoryRows` 中间态(显式启用时提供)."""


__all__ = (
    "ExecutionRequest",
    "ExecutionResult",
    "ObservabilitySpec",
)
