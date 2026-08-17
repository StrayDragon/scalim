"""执行契约(`DSL` 无关).

说明:
- 本模块仅包含纯 `contracts`(数据结构),不包含执行编排逻辑.
- 运行时需兼容 `Python 3.6`.
"""

import warnings
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple, Union

from ..sinks import ISink
from ..sinks.accept_types import SinkTypePrecheck
from ..typedefs import KeyNormalizationMode, ParallelMode, RowData, RuntimeValue
from ..vendor.dataclassesx import dataclass
from ..vendor.dataclassesx import field as dataclass_field
from .excel_column_residency import ExcelColumnResidency
from .lookup_chunking import normalize_optional_max_chunk_workers
from .output_contracts import ExportLayout, OutputSpec
from .output_write_layout import OutputWriteLayout

if TYPE_CHECKING:
    from ..hooks import IExecutionHook
    from ..ob.observer import Observer
    from ..ob.presets.viz import VizObserverConfig
    from ..planning.plan import ExecutionPlan
    from ..sinks.memory import InMemoryCsv
    from ..sinks.rows import InMemoryRows
    from ..spec.ir import DemandIr
    from .guardrails import GuardrailsPolicy
    from .loader_retry import LoaderRetryPolicies
    from .output_composition import OutputCompositionSpec, OutputTargetStats
    from .runtime_bindings import RuntimeBindings


_ADAPTIVE_MAX_WORKERS_HARD_CAP = 256


@dataclass(frozen=True)
class ObservabilitySpec:
    """与 `DSL` 无关的可观测性请求(用于运行编排).

    - `viz_config` 可选;在构建执行计划后会物化为 `VizObserver`.
    """

    fallback_logger_enabled: bool = False
    viz_config: Optional["VizObserverConfig"] = None


def _validate_execution_request_export_layout(export_layout: RuntimeValue) -> None:
    if not isinstance(export_layout, ExportLayout):
        msg = "ExecutionRequest.export_layout must be an ExportLayout"
        raise TypeError(msg)


def _validate_execution_request_output(output: RuntimeValue) -> None:
    if not isinstance(output, OutputSpec):
        msg = "ExecutionRequest.output must be an OutputSpec"
        raise TypeError(msg)


def _validate_execution_request_sink(sink: RuntimeValue) -> None:
    if sink is None:
        return

    if not isinstance(sink, ISink):
        msg = "ExecutionRequest.sink must be an ISink or None"
        raise TypeError(msg)


def _validate_execution_request_batch_size(batch_size: Optional[int]) -> None:
    if batch_size is None:
        return

    if isinstance(batch_size, bool) or not isinstance(batch_size, int):
        msg = "ExecutionRequest.batch_size must be an int >= 1 or None"
        raise TypeError(msg)
    if int(batch_size) < 1:
        msg = "ExecutionRequest.batch_size must be >= 1 when provided"
        raise ValueError(msg)


def _validate_execution_request_max_workers(max_workers: int) -> None:
    if isinstance(max_workers, bool) or not isinstance(max_workers, int):
        msg = "ExecutionRequest.max_workers must be an int"
        raise TypeError(msg)
    if int(max_workers) < 0:
        msg = "ExecutionRequest.max_workers must be >= 0"
        raise ValueError(msg)
    if int(max_workers) > _ADAPTIVE_MAX_WORKERS_HARD_CAP:
        msg = "".join(
            [
                f"ExecutionRequest.max_workers is extremely large ({int(max_workers)}). ",
                "adaptive guardrails will cap it at runtime; ",
                "prefer smaller values and treat external inputs as untrusted.",
            ]
        )
        warnings.warn(msg, stacklevel=2)


def _validate_execution_request_parallel_mode(parallel_mode: RuntimeValue) -> None:
    if parallel_mode not in ("seq", "adaptive"):
        msg = "ExecutionRequest.parallel_mode must be 'seq' or 'adaptive'"
        raise ValueError(msg)


def _validate_execution_request_chunk_parallelism(parallelize_lookup_chunks: RuntimeValue, max_chunk_workers: Optional[int]) -> None:
    if not isinstance(parallelize_lookup_chunks, bool):
        msg = "ExecutionRequest.parallelize_lookup_chunks must be a boolean"
        raise TypeError(msg)
    _ = normalize_optional_max_chunk_workers(
        max_chunk_workers,
        label="ExecutionRequest.max_chunk_workers",
    )


def _validate_execution_request_capture_in_memory_rows(capture_in_memory_rows: RuntimeValue) -> None:
    if not isinstance(capture_in_memory_rows, bool):
        msg = "ExecutionRequest.capture_in_memory_rows must be a boolean"
        raise TypeError(msg)


def _validate_execution_request_key_normalization(key_normalization: RuntimeValue) -> None:
    if not isinstance(key_normalization, str):
        msg = "ExecutionRequest.key_normalization must be a string"
        raise TypeError(msg)


def _validate_execution_request_excel_column_residency(excel_column_residency: RuntimeValue) -> None:
    if not isinstance(excel_column_residency, ExcelColumnResidency):
        msg = "ExecutionRequest.excel_column_residency must be an ExcelColumnResidency"
        raise TypeError(msg)


def _validate_execution_request_output_write_layout(output_write_layout: RuntimeValue) -> None:
    if output_write_layout is None:
        return
    if not isinstance(output_write_layout, OutputWriteLayout):
        msg = "ExecutionRequest.output_write_layout must be an OutputWriteLayout or None"
        raise TypeError(msg)


def _validate_execution_request_sink_type_precheck(sink_type_precheck: RuntimeValue) -> None:
    if not isinstance(sink_type_precheck, SinkTypePrecheck):
        msg = "ExecutionRequest.sink_type_precheck must be a SinkTypePrecheck"
        raise TypeError(msg)


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
    """最大并发工作数提示(`0` 表示自动).

    注意:
    - 在 `parallel_mode="adaptive"` 下,显式 `max_workers > 0` 会被 `guardrails` 施加 `hard cap`,
      且当发生裁剪时会发出 `warning`(避免外部输入不受控放大并发).
    """

    parallelize_lookup_chunks: bool = False
    """是否允许 `lookup_chunk_size` 分片并行(默认关闭).

    注意:
    - 仅当 `parallel_mode="adaptive"` 时生效;`seq` 永不分片并行.
    - `lookup_chunk_size` 本身**不是**并行开关(它只表示分片大小).
    - 开启后会放大对外部系统的瞬时并发;全局在途 `ref-loader` 帽 = 解析后的 `adaptive` `workers` `W`.
    - `loader_call` 回调可能直接发生在分片工作线程上(非主线程回放),订阅方须自行保证线程安全.
    """

    max_chunk_workers: Optional[int] = None
    """可选:单步分片扇出上限(`None` 表示仅受全局在途帽 `W` 与分片数限制)."""

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
    """可选:捕获本次运行输出的 `InMemoryRows`(表格总线细胞为 `object`;默认关闭)."""

    excel_column_residency: ExcelColumnResidency = ExcelColumnResidency.BUFFERED
    """列式 `Excel` 文件 `sink` 驻留策略(仅 `format=excel` 且 `streaming=False` 时生效)."""

    output_write_layout: Optional[OutputWriteLayout] = None
    """可选:显式文件写出布局(`None`=按 `streaming`/`residency` 推导;仅接受 `OutputWriteLayout`)."""

    sink_type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF
    """写出前按 `sink` `accept set` 预检(默认 `OFF`)."""

    def __post_init__(self) -> None:
        _validate_execution_request_export_layout(self.export_layout)
        _validate_execution_request_output(self.output)
        _validate_execution_request_sink(self.sink)
        _validate_execution_request_batch_size(self.batch_size)
        _validate_execution_request_max_workers(self.max_workers)
        _validate_execution_request_parallel_mode(self.parallel_mode)
        _validate_execution_request_chunk_parallelism(self.parallelize_lookup_chunks, self.max_chunk_workers)
        _validate_execution_request_capture_in_memory_rows(self.capture_in_memory_rows)
        _validate_execution_request_key_normalization(self.key_normalization)
        _validate_execution_request_excel_column_residency(self.excel_column_residency)
        _validate_execution_request_output_write_layout(self.output_write_layout)
        _validate_execution_request_sink_type_precheck(self.sink_type_precheck)


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
