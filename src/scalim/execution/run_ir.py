import contextlib
import time
import warnings as py_warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .._internal.utils.loader_result import LoaderResultPolicy, normalize_loader_result_policy
from .._internal.warningsx import ScalimExperimentalWarning
from ..events import Event, EventType, generate_run_id
from ..hooks import HookManager
from ..ob.components import split_components
from ..ob.hub import InstrumentationHub
from ..ob.observability import Observability, ObservabilityOptions
from ..ob.presets.viz import VizObserver, VizObserverConfig
from ..ob.structured_logging import log_context, maybe_install_jsonl_logging_from_env
from ..planning.builder import PlanBuilder
from ..planning.plan import ExecutionPlan
from ..sinks import (
    BaseRowSink,
    BaseSink,
    ColumnBatch,
    ColumnCSVSink,
    ColumnExcelSink,
    ColumnValues,
    CSVSink,
    ExcelSink,
    IColumnSink,
    IRowSink,
    ISink,
)
from ..sinks.memory import InMemoryCsv
from ..sinks.rows import InMemoryRows, InMemoryRowsSink
from ..spec.ir import DemandIr, DerivedFieldIr, FieldIr, SupportedFieldIr
from ..typedefs import RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import dataclass, replace
from .adaptive.capture import HookCaptureManager, HookRecordedEvent
from .contracts import ExecutionRequest, ExecutionResult, ObservabilitySpec
from .engine import ScalimEngine
from .key_normalization import normalize_key_normalization
from .output_composition import build_output_composition, required_demand_fields
from .output_contracts import ExportLayout, OutputSpec

if TYPE_CHECKING:
    from ..ob.manager import ObserverManager
    from .output_composition import ManagedArtifactPlan, OutputCompositionSpec, OutputTargetStats, RouterRowSink


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


class _TeeBatchSink(BaseSink):
    _primary: ISink
    _secondary: ISink

    def __init__(self, primary: ISink, secondary: ISink) -> None:
        self._primary = primary
        self._secondary = secondary

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._primary.write_batch(rows)
        self._secondary.write_batch(rows)

    @override
    def close(self) -> None:
        self._primary.close()
        self._secondary.close()


def _create_engine_sink_for_in_memory_rows_capture(
    *,
    sink: ISink,
    field_ids: Sequence[str],
) -> Tuple[ISink, InMemoryRowsSink]:
    rows_sink = InMemoryRowsSink(field_ids=field_ids)
    if isinstance(sink, IColumnSink):
        msg = "capture_in_memory_rows currently requires an IRowSink/ISink output (got IColumnSink)"
        raise TypeError(msg)
    if isinstance(sink, IRowSink):
        return _TeeRowSink(sink, rows_sink), rows_sink
    return _TeeBatchSink(sink, rows_sink), rows_sink


def _prepare_engine_sink(
    *,
    sink: ISink,
    field_ids: Sequence[str],
    capture_in_memory_rows: bool,
    observer_manager: object,
) -> Tuple[ISink, Optional[InMemoryRowsSink]]:
    if not capture_in_memory_rows:
        return sink, None
    try:
        return _create_engine_sink_for_in_memory_rows_capture(
            sink=sink,
            field_ids=field_ids,
        )
    except Exception:
        with contextlib.suppress(Exception):
            sink.close()
        with contextlib.suppress(Exception):
            close = getattr(observer_manager, "close", None)  # pragma: allow-dynattr optional-interface: observer_manager
            if callable(close):
                _ = close()
        raise


def _wrap_sink_for_row_count(sink: ISink, tracker: InternalStatsCollector) -> ISink:
    if isinstance(sink, IColumnSink):
        return _CountingColumnSink(sink, tracker)
    if isinstance(sink, IRowSink):
        return _CountingRowSink(sink, tracker)
    return _CountingBatchSink(sink, tracker)


def _get_field_name(field_id: str, field_ir: SupportedFieldIr) -> str:
    name = field_ir.name
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
        if output.streaming:
            return ExcelSink(
                output_path=str(output.path),
                field_names=field_names,
                header_names=header_names,
                sheet_name=str(output.sheet_name) if output.sheet_name else "Sheet1",
                include_header=output.include_header,
                allow_formulas=bool(output.excel_allow_formulas),
            )
        return ColumnExcelSink(
            output_path=str(output.path),
            field_names=field_names,
            header_names=header_names,
            sheet_name=str(output.sheet_name) if output.sheet_name else "Sheet1",
            include_header=output.include_header,
            allow_formulas=bool(output.excel_allow_formulas),
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
            "ExecutionRequest.sink: Incompatible sinks for tee: file_sink={}({}) vs sink={}({}). "
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
    managed_artifact_plans: Optional[Dict[str, "ManagedArtifactPlan"]]
    composition_router: Optional["RouterRowSink"]


def _collect_workflow_managed_output_export_headers(
    spec: Optional["OutputCompositionSpec"],
) -> Optional[Dict[str, Tuple[str, ...]]]:
    if spec is None:
        return None

    headers: Dict[str, Tuple[str, ...]] = {}
    for target in spec.targets:
        if not target.in_memory or target.workflow_export_header is None:
            continue
        headers[str(target.target_id)] = tuple(str(x) for x in target.workflow_export_header)
    for target in spec.derived_targets:
        if not target.in_memory or target.workflow_export_header is None:
            continue
        headers[str(target.target_id)] = tuple(str(x) for x in target.workflow_export_header)
    return headers or None


def _build_execution_plan(demand_ir: DemandIr, request: ExecutionRequest) -> ExecutionPlan:
    plan_targets: List[str] = list(request.export_layout.field_ids)
    if request.output_composition is not None:
        plan_targets = list(required_demand_fields(request.output_composition))
    return PlanBuilder(demand_ir).build(targets=plan_targets)


def _build_observer_and_hook_managers(
    *,
    plan: ExecutionPlan,
    request: ExecutionRequest,
    run_id: str,
    event_meta_defaults: Optional[Dict[str, Any]] = None,
) -> Tuple["ObserverManager", HookManager, Optional[VizObserver]]:
    fallback_logger_enabled = False
    viz_config: Optional[VizObserverConfig] = None
    if request.observability is not None:
        fallback_logger_enabled = request.observability.fallback_logger_enabled
        viz_config = request.observability.viz_config

    observer_manager = Observability(options=ObservabilityOptions(fallback_logger_enabled=fallback_logger_enabled)).build_manager(
        run_id=str(run_id),
        event_meta_defaults=event_meta_defaults,
    )

    component_observers, component_hooks = split_components(request.components)
    for observer in component_observers:
        observer_manager.register(observer)

    viz_observer: Optional[VizObserver] = None
    if viz_config is not None:
        viz_observer = VizObserver.from_plan(plan, viz_config, output_composition=request.output_composition)
        observer_manager.register(viz_observer)

    hook_manager = HookManager(fallback_logger_enabled=fallback_logger_enabled)
    for hook in component_hooks:
        hook_manager.register(hook)

    return observer_manager, hook_manager, viz_observer


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


def _emit_key_normalization_warning_if_needed(
    *,
    request: ExecutionRequest,
    hook_manager: HookManager,
    observer_manager: "ObserverManager",
) -> None:
    if request.key_normalization == "raw":
        return
    msg = "EXPERIMENTAL: key_normalization='{}' is enabled; semantics may change in future releases.".format(request.key_normalization)

    hooks_want = hook_manager.wants_typed(EventType.DIAGNOSTIC_WARNING)
    event_want = observer_manager.wants(EventType.DIAGNOSTIC_WARNING) or hook_manager.wants_on_event(EventType.DIAGNOSTIC_WARNING)
    has_visible_channel = hooks_want or event_want or hook_manager.fallback_logger_enabled or observer_manager.fallback_logger_enabled

    if has_visible_channel:
        instrumentation = InstrumentationHub(hook_manager=hook_manager, observer_manager=observer_manager)
        instrumentation.emit_diagnostic_warning(
            message=msg,
            source_id="(run)",
            field_id="(run)",
            lookup_key=None,
            row_id="(run)",
            sample_once=True,
        )
        return

    py_warnings.warn(
        msg,
        category=ScalimExperimentalWarning,
        stacklevel=2,
    )


def _collect_managed_artifact_outputs(
    managed_artifact_plans: Optional[Dict[str, "ManagedArtifactPlan"]],
) -> Tuple[Optional[Dict[str, InMemoryRows]], Optional[Dict[str, InMemoryCsv]]]:
    if managed_artifact_plans is None:
        return None, None

    rows_map: Dict[str, InMemoryRows] = {}
    csv_map: Dict[str, InMemoryCsv] = {}
    for target_id, plan_obj in managed_artifact_plans.items():
        rows_artifact = plan_obj.to_rows_artifact()
        if rows_artifact is not None:
            rows_map[str(target_id)] = rows_artifact
        csv_artifact = plan_obj.to_csv_artifact()
        if csv_artifact is not None:
            csv_map[str(target_id)] = csv_artifact
    return rows_map or None, csv_map or None


def _build_execution_result(
    *,
    demand_ir: DemandIr,
    plan: ExecutionPlan,
    request: ExecutionRequest,
    output_assembly: _OutputAssembly,
    stats: InternalStatsCollector,
    start_time: float,
    in_memory_rows_sink: Optional[InMemoryRowsSink],
) -> ExecutionResult:
    output_target_stats: Optional[List["OutputTargetStats"]] = None
    if output_assembly.composition_router is not None:
        output_target_stats = output_assembly.composition_router.get_target_stats()

    in_memory_rows_outputs, in_memory_csv_outputs = _collect_managed_artifact_outputs(output_assembly.managed_artifact_plans)
    workflow_managed_output_export_headers = _collect_workflow_managed_output_export_headers(request.output_composition)
    in_memory_rows = in_memory_rows_sink.to_artifact() if in_memory_rows_sink is not None else None

    return ExecutionResult(
        output_path=output_assembly.output_path,
        total_rows=stats.total_rows,
        duration=time.perf_counter() - start_time,
        demand_ir=demand_ir,
        plan=plan,
        outputs=output_assembly.outputs,
        output_target_stats=output_target_stats,
        in_memory_csv_outputs=in_memory_csv_outputs,
        in_memory_rows_outputs=in_memory_rows_outputs,
        workflow_managed_output_export_headers=workflow_managed_output_export_headers,
        in_memory_rows=in_memory_rows,
    )


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
            managed_artifact_plans=None,
            composition_router=None,
        )

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
        run_key_normalization=request.key_normalization,
        instrumentation=instrumentation,
    )

    router_sink = composition_plan.sink
    composed_sink: ISink = router_sink
    if request.sink is not None:
        try:
            composed_sink = _create_tee_sink(router_sink, request.sink)
        except ValueError as e:
            msg = (
                "ExecutionRequest.sink: Incompatible sinks for tee: composed_sink={}({}) vs sink={}({}). "
                "Both sinks must be IRowSink (output_composition only supports streaming row sinks). "
                "Hint: use InMemoryRowDataSink (or another IRowSink) when teeing with composed outputs."
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
        managed_artifact_plans=composition_plan.managed_artifact_plans or None,
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
    runtime_bindings = request.runtime_bindings
    if runtime_bindings is None:
        msg = "ExecutionRequest.runtime_bindings is required (missing runtime linking stage)"
        raise ValueError(msg)
    try:
        return engine_cls(
            demand=demand_ir,
            plan=plan,
            runtime_bindings=runtime_bindings,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            guardrails=request.guardrails,
            loader_retry=request.loader_retry,
            batch_size=batch_size,
            parallel_mode=request.parallel_mode,
            max_workers=request.max_workers,
            key_normalization=request.key_normalization,
        )
    except Exception:
        with contextlib.suppress(Exception):
            sink.close()
        with contextlib.suppress(Exception):
            observer_manager.close()
        raise


def _run_ir_with_plan_and_managers(
    demand_ir: DemandIr,
    plan: ExecutionPlan,
    request: ExecutionRequest,
    *,
    hook_manager: HookManager,
    observer_manager: "ObserverManager",
    wall_start_time: float,
    start_time: float,
    engine_factory: Optional[Callable[..., ScalimEngine]] = None,
) -> ExecutionResult:
    _emit_key_normalization_warning_if_needed(
        request=request,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
    )

    stats = InternalStatsCollector()
    batch_size = request.batch_size

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

    engine_sink, in_memory_rows_sink = _prepare_engine_sink(
        sink=output_assembly.counting_sink,
        field_ids=list(plan.target_fields),
        capture_in_memory_rows=bool(request.capture_in_memory_rows),
        observer_manager=observer_manager,
    )

    run_ok = False
    try:
        _ = engine.run(main_rows=request.main_rows, sink=engine_sink)
        run_ok = True
    finally:
        # 尽力清理: 即使 `engine`/`pipeline` 在关闭前失败也要执行.
        #
        # 语义:
        # - `engine.run(...)` 成功: `sink.close()` 失败必须传播(输出落盘/提交的真实成功标准).
        # - `engine.run(...)` 失败: `sink.close()` 尽力而为,不得覆盖原异常.
        if run_ok:
            try:
                engine_sink.close()
            finally:
                with contextlib.suppress(Exception):
                    observer_manager.close()
        else:
            with contextlib.suppress(Exception):
                engine_sink.close()
            with contextlib.suppress(Exception):
                observer_manager.close()

    return _build_execution_result(
        demand_ir=demand_ir,
        plan=plan,
        request=request,
        output_assembly=output_assembly,
        stats=stats,
        start_time=start_time,
        in_memory_rows_sink=in_memory_rows_sink,
    )


@dataclass
class _RunIrBootstrap:
    """`run_ir` 和 `run_ir_capture_events` 共享的预计算状态."""

    run_id: str
    plan: ExecutionPlan
    request: ExecutionRequest
    ctx: Dict[str, Any]
    start_time: float
    wall_start_time: float


def _bootstrap_run_ir(
    demand_ir: DemandIr,
    request: ExecutionRequest,
    event_meta_defaults: Optional[Dict[str, Any]] = None,
) -> _RunIrBootstrap:
    maybe_install_jsonl_logging_from_env()
    run_id = generate_run_id(prefix="run")

    ctx: Dict[str, Any] = {"run_id": str(run_id)}
    if demand_ir.name:
        ctx["demand"] = str(demand_ir.name)
    if event_meta_defaults:
        for key in ("workflow_exec_id", "workflow_node_id", "workflow_node_decl_order", "demand_path"):
            if key in event_meta_defaults:
                ctx[key] = event_meta_defaults[key]

    start_time = time.perf_counter()
    wall_start_time = time.time()

    request = replace(request, key_normalization=normalize_key_normalization(request.key_normalization))
    plan = _build_execution_plan(demand_ir, request)

    return _RunIrBootstrap(
        run_id=str(run_id),
        plan=plan,
        request=request,
        ctx=ctx,
        start_time=start_time,
        wall_start_time=wall_start_time,
    )


def run_ir_capture_events(
    demand_ir: DemandIr,
    request: ExecutionRequest,
    engine_factory: Optional[Callable[..., ScalimEngine]] = None,
    event_meta_defaults: Optional[Dict[str, Any]] = None,
) -> Tuple[ExecutionResult, List[HookRecordedEvent], List[Event], Optional[VizObserver]]:
    """运行一次 `demand IR`,但不调用用户 `hooks/observers`;改为捕获事件供上层按确定顺序回放.

    主要用于工作流并发执行时实现 `capture+replay`.
    """
    boot = _bootstrap_run_ir(demand_ir, request, event_meta_defaults)

    with log_context(**boot.ctx):
        replay_observer_manager, replay_hook_manager, viz_observer = _build_observer_and_hook_managers(
            plan=boot.plan,
            request=boot.request,
            run_id=boot.run_id,
            event_meta_defaults=event_meta_defaults,
        )

        hook_manager = HookCaptureManager(replay_hook_manager)
        hook_manager.loader_result_policy = normalize_loader_result_policy(LoaderResultPolicy.SUMMARY)
        observer_manager = replay_observer_manager.create_capture_manager()
        observer_manager.loader_result_policy = normalize_loader_result_policy(LoaderResultPolicy.SUMMARY)
        observer_manager.max_recorded_events = None

        result = _run_ir_with_plan_and_managers(
            demand_ir,
            boot.plan,
            boot.request,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            wall_start_time=boot.wall_start_time,
            start_time=boot.start_time,
            engine_factory=engine_factory,
        )
        hook_events = hook_manager.drain_events()
        events = observer_manager.drain_events()
        return result, hook_events, events, viz_observer


def run_ir(
    demand_ir: DemandIr,
    request: ExecutionRequest,
    engine_factory: Optional[Callable[..., ScalimEngine]] = None,
    event_meta_defaults: Optional[Dict[str, Any]] = None,
) -> ExecutionResult:
    boot = _bootstrap_run_ir(demand_ir, request, event_meta_defaults)

    with log_context(**boot.ctx):
        observer_manager, hook_manager, _viz_observer = _build_observer_and_hook_managers(
            plan=boot.plan,
            request=boot.request,
            run_id=boot.run_id,
            event_meta_defaults=event_meta_defaults,
        )
        return _run_ir_with_plan_and_managers(
            demand_ir,
            boot.plan,
            boot.request,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            wall_start_time=boot.wall_start_time,
            start_time=boot.start_time,
            engine_factory=engine_factory,
        )


__all__ = (
    "ExecutionRequest",
    "ExecutionResult",
    "ExportLayout",
    "ObservabilitySpec",
    "OutputSpec",
    "export_layout_from_demand_ir",
    "run_ir",
)
