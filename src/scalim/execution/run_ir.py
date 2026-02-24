import contextlib
import time
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

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
    """DSL-agnostic export layout.

    This object defines:
    - which fields are targeted (and their order)
    - optional header names aligned with the field order
    """

    field_ids: tuple[str, ...]
    header_names: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.header_names is not None and len(self.header_names) != len(self.field_ids):
            msg = "ExportLayout.header_names must align with field_ids"
            raise ValueError(msg)


@dataclass(frozen=True)
class OutputSpec:
    """DSL-agnostic output strategy.

    When `path` is falsy (None/""), no file sink will be created.
    """

    format: str = "csv"
    path: str | None = None
    encoding: str = "utf-8"
    streaming: bool = True
    include_header: bool = True


@dataclass(frozen=True)
class ObservabilitySpec:
    """DSL-agnostic observability request for run orchestration.

    - `viz_config` is optional and will be materialized to a `VizObserver` after plan is built.
    """

    fallback_logger_enabled: bool = False
    viz_config: VizObserverConfig | None = None


@dataclass(frozen=True)
class ExecutionRequest:
    export_layout: ExportLayout
    output: OutputSpec = dataclass_field(default_factory=OutputSpec)
    sink: ISink | None = None
    observability: ObservabilitySpec | None = None
    components: list[Observer | IExecutionHook] | None = None
    batch_size: int | None = None
    parallel_mode: ParallelMode = "seq"
    max_workers: int = 0
    guardrails: GuardrailsPolicy | None = None
    loader_retry: LoaderRetryPolicies | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """DSL-agnostic execution result.

    Note:
    - `total_rows` counts rows emitted to the effective sink (including `NullSink`). This is an output/emit row count.
    - Observability metrics may use a different definition for low-overhead throughput estimates
      (e.g. `PerformanceMetrics.total_rows` counts input `row_ids`).
    """

    output_path: str | None
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
    output_path: str | None


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
    """Internal execution stats collector.

    This object is intentionally lightweight and DSL-agnostic.
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
    """Helper for adapters to build an ExportLayout from effective IR."""
    normalized_ids = tuple(str(item) for item in field_ids)
    if header_fields_output_by != "name":
        return ExportLayout(field_ids=normalized_ids, header_names=None)

    name_map: dict[str, str] = {}
    for fid in normalized_ids:
        field_ir = demand_ir.fields.get(fid)
        if field_ir is None:
            continue
        resolved = _get_field_name(fid, field_ir)
        if resolved != fid:
            name_map[fid] = resolved

    if not name_map:
        return ExportLayout(field_ids=normalized_ids, header_names=None)

    header_names: tuple[str, ...] = tuple(name_map.get(fid, fid) for fid in normalized_ids)
    return ExportLayout(field_ids=normalized_ids, header_names=header_names)


def _create_file_sink(output: OutputSpec, layout: ExportLayout) -> ISink | None:
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

    msg = f"Unsupported output format: '{output.format}'. Supported formats: excel, csv."
    raise ValueError(msg)


def _create_tee_sink(primary: ISink, secondary: ISink) -> ISink:
    if isinstance(primary, IRowSink) and isinstance(secondary, IRowSink):
        return _TeeRowSink(primary, secondary)
    if isinstance(primary, IColumnSink) and isinstance(secondary, IColumnSink):
        return _TeeColumnSink(primary, secondary)
    msg = f"Incompatible sinks for tee: {type(primary).__name__} vs {type(secondary).__name__}"
    raise ValueError(msg)


def _describe_sink_kind(sink: ISink) -> str:
    if isinstance(sink, IRowSink):
        return "IRowSink"
    if isinstance(sink, IColumnSink):
        return "IColumnSink"
    return "ISink"


def _create_output_plan(output: OutputSpec, layout: ExportLayout, sink: ISink | None) -> _OutputPlan:
    file_sink = _create_file_sink(output, layout)
    output_path: str | None = output.path or None

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
            f"Incompatible sinks for tee: file_sink={type(file_sink).__name__}"
            f"({_describe_sink_kind(file_sink)}) vs sink={type(sink).__name__}"
            f"({_describe_sink_kind(sink)}). "
            "Both sinks must be IRowSink or both must be IColumnSink. "
            "Hint: set output.streaming=true for a row file sink (CSV/Excel) when teeing with an IRowSink; "
            "or use a column sink such as InMemoryColumnSink when output.streaming=false. "
            "If you pass a custom sink, it must implement IRowSink or IColumnSink to be tee-compatible."
        )
        with contextlib.suppress(Exception):
            file_sink.close()
        raise ValueError(msg) from e

    return _OutputPlan(sink=tee_sink, output_path=output_path)


def run_ir(demand_ir: DemandIr, request: ExecutionRequest) -> ExecutionResult:
    start_time = time.perf_counter()

    plan = PlanBuilder(demand_ir).build(targets=list(request.export_layout.field_ids))

    fallback_logger_enabled = False
    viz_config: VizObserverConfig | None = None
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

    try:
        engine = ScalimEngine(
            demand=demand_ir,
            plan=plan,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            guardrails=request.guardrails,
            loader_retry=request.loader_retry,
            batch_size=request.batch_size or demand_ir.batch_size_hint,
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
        # Best-effort cleanup even if engine/pipeline fails before closing.
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
