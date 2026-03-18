import contextlib
import time
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..hooks.base import HookManager, IExecutionHook
from ..ob.components import split_components
from ..ob.hub import InstrumentationHub
from ..ob.observability import Observability
from ..ob.observer import Observer
from ..ob.presets.viz import VizObserver, VizObserverConfig
from ..planning.builder import PlanBuilder
from ..planning.plan import ExecutionPlan
from ..sinks.sink_base import BaseRowSink, BaseSink, ColumnBatch, ColumnValues, IColumnSink, IRowSink, ISink
from ..sinks.sink_csv import ColumnCSVSink, CSVSink
from ..spec.ir.demand import DemandIr
from ..spec.ir.fields import DerivedFieldIr, FieldIr, SupportedFieldIr
from ..typedefs import ParallelMode, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import override
from .engine import ScalimEngine
from .guardrails import GuardrailsPolicy
from .loader_retry import LoaderRetryPolicies
from .output_contracts import ExportLayout, OutputSpec

if TYPE_CHECKING:
    from ..ob.manager import ObserverManager
    from .output_composition import OutputCompositionSpec, OutputTargetStats, RouterRowSink


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

    output_composition: Optional["OutputCompositionSpec"] = None
    """可选:多输出组合请求(`IR/Python-only`).

    当提供该字段时:
    - `output`/`sink` 的单输出装配将被忽略
    - 运行计划的目标字段将由组合请求的 `required_demand_fields` 计算得出
    """


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
    outputs: Optional[Dict[str, str]] = None
    """可选:输出目标到 `output_path` 的映射(多输出组合时提供)."""

    output_target_stats: Optional[List["OutputTargetStats"]] = None
    """可选:每个输出目标的统计(行数/耗时/错误/禁用)(多输出组合时提供)."""


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
                sheet_name=str(output.sheet_name) if output.sheet_name else "Sheet1",
                include_header=output.include_header,
                allow_formulas=bool(output.excel_allow_formulas),
                write_lock=bool(output.write_lock),
            )
        return ColumnExcelSink(
            output_path=str(output.path),
            field_names=field_names,
            header_names=header_names,
            sheet_name=str(output.sheet_name) if output.sheet_name else "Sheet1",
            include_header=output.include_header,
            allow_formulas=bool(output.excel_allow_formulas),
            write_lock=bool(output.write_lock),
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


@dataclass(frozen=True)
class _OutputAssembly:
    counting_sink: ISink
    output_path: Optional[str]
    outputs: Optional[Dict[str, str]]
    composition_router: Optional["RouterRowSink"]


def _build_execution_plan(demand_ir: DemandIr, request: ExecutionRequest) -> ExecutionPlan:
    plan_targets: List[str] = list(request.export_layout.field_ids)
    if request.output_composition is not None:
        from .output_composition import required_demand_fields  # noqa: PLC0415

        plan_targets = list(required_demand_fields(request.output_composition))
    return PlanBuilder(demand_ir).build(targets=plan_targets)


def _build_observer_and_hook_managers(
    *,
    plan: ExecutionPlan,
    request: ExecutionRequest,
    event_meta_defaults: Optional[Dict[str, Any]] = None,
) -> Tuple["ObserverManager", HookManager]:
    fallback_logger_enabled = False
    viz_config: Optional[VizObserverConfig] = None
    if request.observability is not None:
        fallback_logger_enabled = request.observability.fallback_logger_enabled
        viz_config = request.observability.viz_config

    observer_manager = Observability(fallback_logger_enabled=fallback_logger_enabled).build_manager(event_meta_defaults=event_meta_defaults)

    component_observers, component_hooks = split_components(request.components)
    for observer in component_observers:
        observer_manager.register(observer)

    if viz_config is not None:
        observer_manager.register(VizObserver.from_plan(plan, viz_config, output_composition=request.output_composition))

    hook_manager = HookManager(fallback_logger_enabled=fallback_logger_enabled)
    for hook in component_hooks:
        hook_manager.register(hook)

    return observer_manager, hook_manager


def _build_field_fingerprints_for_meta(demand_ir: DemandIr) -> List[Tuple[str, str, str, str]]:
    """生成稳定指纹(不包含可调用对象`callable`),用于元信息工作表."""
    field_fingerprints: List[Tuple[str, str, str, str]] = []
    for field_id in sorted(demand_ir.fields.keys()):
        spec = demand_ir.fields[field_id]
        if isinstance(spec, FieldIr):
            field_fingerprints.append((spec.field_id, "field", str(spec.source.source_id), str(spec.data_key)))
        elif isinstance(spec, DerivedFieldIr):
            field_fingerprints.append((spec.field_id, "derived", "", ",".join(spec.dependencies)))
        else:
            field_fingerprints.append((str(field_id), type(spec).__name__, "", ""))
    return field_fingerprints


def _select_primary_output_path(outputs: Dict[str, str], spec: "OutputCompositionSpec") -> Optional[str]:
    primary_id: Optional[str] = None
    for t in spec.targets:
        if t.is_primary:
            primary_id = str(t.target_id)
            break
    if primary_id is None:
        for t in spec.derived_targets:
            if t.is_primary:
                primary_id = str(t.target_id)
                break

    if primary_id is not None:
        resolved = outputs.get(primary_id)
        if resolved is not None:
            return resolved

    if outputs:
        return next(iter(outputs.values()))
    return None


def _assemble_outputs(
    *,
    demand_ir: DemandIr,
    plan: ExecutionPlan,
    request: ExecutionRequest,
    hook_manager: HookManager,
    observer_manager: "ObserverManager",
    wall_start_time: float,
    batch_size: Optional[int],
    stats: InternalStatsCollector,
) -> _OutputAssembly:
    composition_spec = request.output_composition
    if composition_spec is None:
        output_plan = _create_output_plan(request.output, request.export_layout, request.sink)
        counting_sink = _wrap_sink_for_row_count(output_plan.sink, stats)
        return _OutputAssembly(
            counting_sink=counting_sink,
            output_path=output_plan.output_path,
            outputs=None,
            composition_router=None,
        )

    from .output_composition import build_output_composition  # noqa: PLC0415

    # 构建一个与 `engine` 共享订阅者的 `InstrumentationHub`,用于输出级事件(每个输出目标结束统计).
    instrumentation = InstrumentationHub(hook_manager=hook_manager, observer_manager=observer_manager)

    composition_plan = build_output_composition(
        spec=composition_spec,
        demand_name=str(demand_ir.name),
        demand_main_source_id=str(demand_ir.main_source.source_id),
        demand_target_fields=list(plan.target_fields),
        demand_field_fingerprints=_build_field_fingerprints_for_meta(demand_ir),
        run_started_at_epoch=wall_start_time,
        run_parallel_mode=str(request.parallel_mode),
        run_batch_size=batch_size,
        instrumentation=instrumentation,
    )

    router_sink = composition_plan.sink
    composed_sink: ISink = router_sink
    if request.sink is not None:
        try:
            composed_sink = _create_tee_sink(router_sink, request.sink)
        except ValueError as e:
            msg = (
                "Incompatible sinks for tee: composed_sink={}({}) vs sink={}({}). "
                "Both sinks must be IRowSink (output_composition only supports streaming row sinks). "
                "Hint: use InMemoryRowSink (or another IRowSink) when teeing with composed outputs."
            ).format(
                type(router_sink).__name__,
                _describe_sink_kind(router_sink),
                type(request.sink).__name__,
                _describe_sink_kind(request.sink),
            )
            with contextlib.suppress(Exception):
                router_sink.close()
            raise ValueError(msg) from e

    counting_sink = _wrap_sink_for_row_count(composed_sink, stats)
    outputs = composition_plan.output_paths
    output_path = _select_primary_output_path(outputs, composition_spec) if outputs else None
    return _OutputAssembly(
        counting_sink=counting_sink,
        output_path=output_path,
        outputs=outputs,
        composition_router=router_sink,
    )


def _create_engine_with_cleanup(
    *,
    demand_ir: DemandIr,
    plan: ExecutionPlan,
    request: ExecutionRequest,
    hook_manager: HookManager,
    observer_manager: "ObserverManager",
    batch_size: Optional[int],
    sink: ISink,
    engine_factory: Optional[Callable[..., ScalimEngine]] = None,
) -> ScalimEngine:
    engine_cls = engine_factory or ScalimEngine
    try:
        return engine_cls(
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
            sink.close()
        with contextlib.suppress(Exception):
            observer_manager.close()
        raise


def run_ir(
    demand_ir: DemandIr,
    request: ExecutionRequest,
    engine_factory: Optional[Callable[..., ScalimEngine]] = None,
    event_meta_defaults: Optional[Dict[str, Any]] = None,
) -> ExecutionResult:
    start_time = time.perf_counter()
    wall_start_time = time.time()

    plan = _build_execution_plan(demand_ir, request)
    observer_manager, hook_manager = _build_observer_and_hook_managers(plan=plan, request=request, event_meta_defaults=event_meta_defaults)

    stats = InternalStatsCollector()
    batch_size = request.batch_size if request.batch_size is not None else demand_ir.batch_size_hint

    output_assembly = _assemble_outputs(
        demand_ir=demand_ir,
        plan=plan,
        request=request,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        wall_start_time=wall_start_time,
        batch_size=batch_size,
        stats=stats,
    )

    engine = _create_engine_with_cleanup(
        demand_ir=demand_ir,
        plan=plan,
        request=request,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        batch_size=batch_size,
        sink=output_assembly.counting_sink,
        engine_factory=engine_factory,
    )

    run_ok = False
    try:
        _ = engine.run(sink=output_assembly.counting_sink)
        run_ok = True
    finally:
        # 尽力清理: 即使 `engine`/`pipeline` 在关闭前失败也要执行.
        #
        # 语义:
        # - `engine.run(...)` 成功: `sink.close()` 失败必须传播(输出落盘/提交的真实成功标准).
        # - `engine.run(...)` 失败: `sink.close()` 尽力而为,不得覆盖原异常.
        if run_ok:
            try:
                output_assembly.counting_sink.close()
            finally:
                with contextlib.suppress(Exception):
                    observer_manager.close()
        else:
            with contextlib.suppress(Exception):
                output_assembly.counting_sink.close()
            with contextlib.suppress(Exception):
                observer_manager.close()

    output_target_stats: Optional[List["OutputTargetStats"]] = None
    if output_assembly.composition_router is not None:
        # 注意: `counting_sink.close()` 在 `finally` 中执行;此处读取的是关闭后的最终统计快照.
        output_target_stats = output_assembly.composition_router.get_target_stats()

    return ExecutionResult(
        output_path=output_assembly.output_path,
        total_rows=stats.total_rows,
        duration=time.perf_counter() - start_time,
        demand_ir=demand_ir,
        plan=plan,
        outputs=output_assembly.outputs,
        output_target_stats=output_target_stats,
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
