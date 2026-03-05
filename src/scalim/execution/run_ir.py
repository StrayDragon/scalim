import contextlib
import time
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..hooks.base import HookManager, IExecutionHook
from ..ob.components import split_components
from ..ob.observability import Observability
from ..ob.observer import Observer
from ..ob.presets.viz import VizObserver, VizObserverConfig
from ..planning.builder import PlanBuilder
from ..planning.plan import ExecutionPlan
from ..sinks.sink_base import BaseRowSink, BaseSink, ColumnBatch, ColumnValues, IColumnSink, IRowSink, ISink
from ..sinks.sink_csv import ColumnCSVSink, CSVSink
from ..spec.ir.demand import DemandIr
from ..spec.ir.fields import SupportedFieldIr
from ..typedefs import ParallelMode, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import override
from .engine import ScalimEngine
from .guardrails import GuardrailsPolicy
from .loader_retry import LoaderRetryPolicies


@dataclass(frozen=True)
class ExportLayout:
    """与 `DSL` 无关的导出布局.

    此对象定义:
    - 需要导出的字段(及其顺序)
    - 与字段顺序对齐的可选表头名称
    """

    field_ids: Tuple[str, ...]
    header_names: Optional[Tuple[str, ...]] = None

    def __post_init__(self) -> None:
        if self.header_names is not None and len(self.header_names) != len(self.field_ids):
            msg = "ExportLayout.header_names must align with field_ids"
            raise ValueError(msg)


@dataclass(frozen=True)
class OutputSpec:
    """与 `DSL` 无关的输出策略.

    当 `path` 为假值(`None`/`\"\"`)时,不会创建文件输出端.

    安全提示:
    - `path` 控制文件系统写入(会创建父目录并以原子方式替换目标文件).
    - 仅在 `YAML`/配置输入可信时启用基于文件的输出;否则应在外部校验/覆盖 `path`.
    """

    format: str = "csv"
    path: Optional[str] = None
    encoding: str = "utf-8"
    streaming: bool = True
    include_header: bool = True


@dataclass(frozen=True)
class ObservabilitySpec:
    """与 `DSL` 无关的可观测性请求(用于运行编排).

    - `viz_config` 可选;在构建执行计划后会物化为 `VizObserver`.
    """

    fallback_logger_enabled: bool = False
    viz_config: Optional[VizObserverConfig] = None


@dataclass(frozen=True)
class ExecutionRequest:
    export_layout: ExportLayout
    """导出布局(字段顺序与可选表头)."""

    output: OutputSpec = dataclass_field(default_factory=OutputSpec)
    """输出策略(例如输出格式、路径、编码、是否流式)."""

    sink: Optional[ISink] = None
    """可选:显式指定输出端;若为 `None` 则按 `output` 策略创建."""

    observability: Optional[ObservabilitySpec] = None
    """可选:可观测性请求(例如 `viz` 配置)."""

    components: Optional[List[Union[Observer, IExecutionHook]]] = None
    """可选:要挂载的 `Observer`/`Hook` 组件列表."""

    batch_size: Optional[int] = None
    """可选:覆盖批大小(`None` 表示不覆盖)."""

    parallel_mode: ParallelMode = "seq"
    """并行模式(`seq` 或 `adaptive`)."""

    max_workers: int = 0
    """最大并发工作数提示(`0` 表示自动)."""

    guardrails: Optional[GuardrailsPolicy] = None
    """可选:运行时护栏策略."""

    loader_retry: Optional[LoaderRetryPolicies] = None
    """可选:加载重试策略."""


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
    demand_ir: DemandIr
    plan: ExecutionPlan


class _TeeRowSink(BaseRowSink):
    _primary: IRowSink
    _secondary: IRowSink

    def __init__(self, primary: IRowSink, secondary: IRowSink) -> None:
        self._primary = primary
        self._secondary = secondary

    @override
    def write_row(self, row: RowData) -> None:
        self._primary.write_row(row)
        self._secondary.write_row(row)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._primary.write_batch(rows)
        self._secondary.write_batch(rows)

    @override
    def close(self) -> None:
        self._primary.close()
        self._secondary.close()


@dataclass(frozen=True)
class _OutputPlan:
    sink: ISink
    output_path: Optional[str]


class _TeeColumnSink(IColumnSink):
    _primary: IColumnSink
    _secondary: IColumnSink

    def __init__(self, primary: IColumnSink, secondary: IColumnSink) -> None:
        self._primary = primary
        self._secondary = secondary

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._primary.write_batch(rows)
        self._secondary.write_batch(rows)

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        self._primary.set_row_ids(row_ids)
        self._secondary.set_row_ids(row_ids)

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        self._primary.write_column(field_key, values)
        self._secondary.write_column(field_key, values)

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        self._primary.write_columns(columns)
        self._secondary.write_columns(columns)

    @override
    def close(self) -> None:
        self._primary.close()
        self._secondary.close()


class _NullSink(BaseSink):
    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        _ = rows

    @override
    def close(self) -> None:
        return


class InternalStatsCollector:
    """内部执行统计收集器.

    此对象刻意保持轻量,且与 `DSL` 无关.
    """

    def __init__(self) -> None:
        self.total_rows: int = 0


class _CountingRowSink(BaseRowSink):
    _sink: IRowSink
    _tracker: InternalStatsCollector

    def __init__(self, sink: IRowSink, tracker: InternalStatsCollector) -> None:
        self._sink = sink
        self._tracker = tracker

    @override
    def write_row(self, row: RowData) -> None:
        self._tracker.total_rows += 1
        self._sink.write_row(row)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._tracker.total_rows += len(rows)
        self._sink.write_batch(rows)

    @override
    def close(self) -> None:
        self._sink.close()


class _CountingColumnSink(IColumnSink):
    _sink: IColumnSink
    _tracker: InternalStatsCollector

    def __init__(self, sink: IColumnSink, tracker: InternalStatsCollector) -> None:
        self._sink = sink
        self._tracker = tracker

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        self._tracker.total_rows += len(row_ids)
        self._sink.set_row_ids(row_ids)

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        self._sink.write_column(field_key, values)

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        self._sink.write_columns(columns)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._tracker.total_rows += len(rows)
        self._sink.write_batch(rows)

    @override
    def close(self) -> None:
        self._sink.close()


class _CountingBatchSink(ISink):
    _sink: ISink
    _tracker: InternalStatsCollector

    def __init__(self, sink: ISink, tracker: InternalStatsCollector) -> None:
        self._sink = sink
        self._tracker = tracker

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._tracker.total_rows += len(rows)
        self._sink.write_batch(rows)

    @override
    def close(self) -> None:
        self._sink.close()


def _wrap_sink_for_row_count(sink: ISink, tracker: InternalStatsCollector) -> ISink:
    if isinstance(sink, IColumnSink):
        return _CountingColumnSink(sink, tracker)
    if isinstance(sink, IRowSink):
        return _CountingRowSink(sink, tracker)
    return _CountingBatchSink(sink, tracker)


def _get_field_name(field_id: str, field_ir: SupportedFieldIr) -> str:
    name = getattr(field_ir, "name", "") or ""
    if name and name != field_id:
        return name
    return field_id


def export_layout_from_demand_ir(
    demand_ir: DemandIr,
    field_ids: Sequence[str],
    *,
    header_fields_output_by: str = "field_id",
) -> ExportLayout:
    """供适配器根据生效 `IR` 构建 `ExportLayout` 的辅助函数."""
    normalized_ids = tuple(str(item) for item in field_ids)
    if header_fields_output_by != "name":
        return ExportLayout(field_ids=normalized_ids, header_names=None)

    name_map: Dict[str, str] = {}
    for fid in normalized_ids:
        field_ir = demand_ir.fields.get(fid)
        if field_ir is None:
            continue
        resolved = _get_field_name(fid, field_ir)
        if resolved != fid:
            name_map[fid] = resolved

    if not name_map:
        return ExportLayout(field_ids=normalized_ids, header_names=None)

    header_names: Tuple[str, ...] = tuple(name_map.get(fid, fid) for fid in normalized_ids)
    return ExportLayout(field_ids=normalized_ids, header_names=header_names)


def _create_file_sink(output: OutputSpec, layout: ExportLayout) -> Optional[ISink]:
    if not output.path:
        return None

    output_path = Path(output.path)
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = (output.format or "csv").lower()
    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else field_names

    if fmt == "csv":
        if output.streaming:
            return CSVSink(
                output_path=str(output.path),
                encoding=output.encoding,
                field_names=field_names,
                header_names=header_names,
                include_header=output.include_header,
                flush_policy="every_n_rows",
            )
        return ColumnCSVSink(
            output_path=str(output.path),
            field_names=field_names,
            header_names=header_names,
            encoding=output.encoding,
            include_header=output.include_header,
        )

    if fmt == "excel":
        from ..sinks.sink_excel import ColumnExcelSink, ExcelSink  # noqa: PLC0415

        if output.streaming:
            return ExcelSink(
                output_path=str(output.path),
                field_names=field_names,
                header_names=header_names,
                include_header=output.include_header,
            )
        return ColumnExcelSink(
            output_path=str(output.path),
            field_names=field_names,
            header_names=header_names,
            include_header=output.include_header,
        )

    msg = "Unsupported output format: '{}'. Supported formats: excel, csv.".format(output.format)
    raise ValueError(msg)


def _create_tee_sink(primary: ISink, secondary: ISink) -> ISink:
    if isinstance(primary, IRowSink) and isinstance(secondary, IRowSink):
        return _TeeRowSink(primary, secondary)
    if isinstance(primary, IColumnSink) and isinstance(secondary, IColumnSink):
        return _TeeColumnSink(primary, secondary)
    msg = "Incompatible sinks for tee: {} vs {}".format(type(primary).__name__, type(secondary).__name__)
    raise ValueError(msg)


def _describe_sink_kind(sink: ISink) -> str:
    if isinstance(sink, IRowSink):
        return "IRowSink"
    if isinstance(sink, IColumnSink):
        return "IColumnSink"
    return "ISink"


def _create_output_plan(output: OutputSpec, layout: ExportLayout, sink: Optional[ISink]) -> _OutputPlan:
    file_sink = _create_file_sink(output, layout)
    output_path: Optional[str] = output.path or None

    if sink is None:
        if file_sink is not None:
            return _OutputPlan(sink=file_sink, output_path=output_path)
        return _OutputPlan(sink=_NullSink(), output_path=None)

    if file_sink is None:
        return _OutputPlan(sink=sink, output_path=None)

    try:
        tee_sink = _create_tee_sink(file_sink, sink)
    except ValueError as e:
        msg = (
            "Incompatible sinks for tee: file_sink={}({}) vs sink={}({}). "
            "Both sinks must be IRowSink or both must be IColumnSink. "
            "Hint: set output.streaming=true for a row file sink (CSV/Excel) when teeing with an IRowSink; "
            "or use a column sink such as InMemoryColumnSink when output.streaming=false. "
            "If you pass a custom sink, it must implement IRowSink or IColumnSink to be tee-compatible."
        ).format(
            type(file_sink).__name__,
            _describe_sink_kind(file_sink),
            type(sink).__name__,
            _describe_sink_kind(sink),
        )
        with contextlib.suppress(Exception):
            file_sink.close()
        raise ValueError(msg) from e

    return _OutputPlan(sink=tee_sink, output_path=output_path)


def run_ir(
    demand_ir: DemandIr,
    request: ExecutionRequest,
    engine_factory: Optional[Callable[..., ScalimEngine]] = None,
) -> ExecutionResult:
    start_time = time.perf_counter()

    plan = PlanBuilder(demand_ir).build(targets=list(request.export_layout.field_ids))

    fallback_logger_enabled = False
    viz_config: Optional[VizObserverConfig] = None
    if request.observability is not None:
        fallback_logger_enabled = request.observability.fallback_logger_enabled
        viz_config = request.observability.viz_config

    observer_manager = Observability(fallback_logger_enabled=fallback_logger_enabled).build_manager()

    component_observers, component_hooks = split_components(request.components)
    for observer in component_observers:
        observer_manager.register(observer)

    if viz_config is not None:
        observer_manager.register(VizObserver.from_plan(plan, viz_config))

    hook_manager = HookManager(fallback_logger_enabled=fallback_logger_enabled)
    for hook in component_hooks:
        hook_manager.register(hook)

    output_plan = _create_output_plan(request.output, request.export_layout, request.sink)
    stats = InternalStatsCollector()
    counting_sink = _wrap_sink_for_row_count(output_plan.sink, stats)
    batch_size = request.batch_size if request.batch_size is not None else demand_ir.batch_size_hint

    try:
        engine_cls = engine_factory or ScalimEngine
        engine = engine_cls(
            demand=demand_ir,
            plan=plan,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            guardrails=request.guardrails,
            loader_retry=request.loader_retry,
            batch_size=batch_size,
            parallel_mode=request.parallel_mode,
            max_workers=request.max_workers,
        )
    except Exception:
        with contextlib.suppress(Exception):
            counting_sink.close()
        with contextlib.suppress(Exception):
            observer_manager.close()
        raise

    try:
        _ = engine.run(sink=counting_sink)
    finally:
        # 尽力清理: 即使 `engine`/`pipeline` 在关闭前失败也要执行.
        with contextlib.suppress(Exception):
            counting_sink.close()
        with contextlib.suppress(Exception):
            observer_manager.close()

    return ExecutionResult(
        output_path=output_plan.output_path,
        total_rows=stats.total_rows,
        duration=time.perf_counter() - start_time,
        demand_ir=demand_ir,
        plan=plan,
    )


__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "ExportLayout",
    "ObservabilitySpec",
    "OutputSpec",
    "export_layout_from_demand_ir",
    "run_ir",
]
