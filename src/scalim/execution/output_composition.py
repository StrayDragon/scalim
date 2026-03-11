from __future__ import absolute_import

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .._project_constants import VERSION as SCALIM_VERSION
from ..events.catalog import EVENT_OUTPUT_TARGET_END
from ..events.events import OutputTargetEndEvent
from ..ob.hub import InstrumentationHub
from ..sinks.sink_base import BaseRowSink, IRowSink
from ..sinks.sink_csv import CSVSink
from ..sinks.sink_excel import ExcelSink, ExcelWorkbookSink
from ..typedefs import RowData
from ..vendor.compact.typing_extensionsx import override
from .derived_outputs import AggMetricSpec, AggregatingRowSink, GroupByAggregator, RankedGroupByAggregator, fingerprint_for_meta
from .output_contracts import ExportLayout, OutputSpec

OutputRowPredicate = Callable[[RowData], bool]


@dataclass(frozen=True)
class OutputTargetSpec:
    """输出目标(`IR/Python-only`).

    - `layout.field_ids` 表示该目标写出的字段顺序(来自输入行 `dict` 取值).
    - `output.sheet_name` 仅在 `excel` 且写入同一工作簿容器时使用.
    """

    target_id: str
    layout: ExportLayout
    output: OutputSpec
    predicate: Optional[OutputRowPredicate] = None
    is_primary: bool = False
    requires: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True)
class DerivedGroupBySpec:
    """派生汇总输出(内置 `group_by`)."""

    group_by: Tuple[str, ...]
    metrics: Tuple[AggMetricSpec, ...]
    max_groups: int = 0
    rank_by: Optional[str] = None
    rank_field_id: str = "rank"
    rank_order: str = "desc"
    top_k: int = 0

    def required_fields(self) -> Tuple[str, ...]:
        agg = GroupByAggregator(group_by=self.group_by, metrics=self.metrics, max_groups=0)
        return agg.required_fields()


@dataclass(frozen=True)
class DerivedOutputTargetSpec:
    """派生输出目标: 从明细流聚合并在 `close()` 时输出."""

    target_id: str
    derived: DerivedGroupBySpec
    output_layout: ExportLayout
    output: OutputSpec
    is_primary: bool = False
    requires: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True)
class MetaSheetSpec:
    """元信息工作表: 以 `key`/`value` 两列写入运行信息与输出统计."""

    target_id: str
    output: OutputSpec
    sheet_name: str


@dataclass(frozen=True)
class AuditSheetSpec:
    """审计工作表: 以结构化行写入派生输出错误等审计信息."""

    target_id: str
    output: OutputSpec
    sheet_name: str


@dataclass(frozen=True)
class OutputCompositionSpec:
    """多输出组合请求.

    `failure_policy`:
    - `all_fail`: 任一目标失败即失败
    - `primary_only`: 非主输出失败将被记录并禁用该输出,不阻断主输出
    """

    targets: Tuple[OutputTargetSpec, ...] = ()
    derived_targets: Tuple[DerivedOutputTargetSpec, ...] = ()
    meta_sheet: Optional[MetaSheetSpec] = None
    audit_sheet: Optional[AuditSheetSpec] = None
    failure_policy: str = "all_fail"


@dataclass(frozen=True)
class OutputTargetStats:
    target_id: str
    input_row_count: int
    row_count: int
    error_count: int
    duration_seconds: float
    disabled: bool
    output_path: Optional[str]
    sheet_name: Optional[str]
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class OutputTargetWriteError(RuntimeError):
    target_id: str

    def __init__(self, target_id: str, exc: Exception) -> None:
        super(OutputTargetWriteError, self).__init__("Output target failed: {}: {}".format(target_id, exc))
        self.target_id = str(target_id)


def _ordered_unique(items: Sequence[str]) -> Tuple[str, ...]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def required_demand_fields(spec: OutputCompositionSpec) -> Tuple[str, ...]:
    """计算一次运行的目标字段列表(去重保序)."""
    fields: List[str] = []
    for target in spec.targets:
        fields.extend([str(x) for x in target.layout.field_ids])
        if target.requires:
            fields.extend([str(x) for x in target.requires])
    for target in spec.derived_targets:
        fields.extend([str(x) for x in target.derived.required_fields()])
        if target.requires:
            fields.extend([str(x) for x in target.requires])
    return _ordered_unique(fields)


def _create_csv_sink(output: OutputSpec, layout: ExportLayout) -> CSVSink:
    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
    return CSVSink(
        output_path=str(output.path),
        encoding=str(output.encoding),
        field_names=field_names,
        header_names=header_names,
        include_header=bool(output.include_header),
        flush_policy="every_n_rows",
    )


def _create_excel_row_sink(output: OutputSpec, layout: ExportLayout) -> ExcelSink:
    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
    sheet_name = str(output.sheet_name) if output.sheet_name else "Sheet1"
    return ExcelSink(
        output_path=str(output.path),
        field_names=field_names,
        header_names=header_names,
        sheet_name=sheet_name,
        include_header=bool(output.include_header),
    )


@dataclass
class _RouteState:
    target_id: str
    sink: IRowSink
    predicate: Optional[OutputRowPredicate]
    is_primary: bool
    output_path: Optional[str]
    sheet_name: Optional[str]
    disabled: bool = False
    input_row_count: int = 0
    error_count: int = 0
    duration_seconds: float = 0.0
    first_error: Optional[Exception] = None
    output_counter: Optional["_RowCounter"] = None


@dataclass
class _RowCounter:
    rows: int = 0


@dataclass
class _FinalTargetState:
    target_id: str
    sink: IRowSink
    output_counter: _RowCounter
    output_path: Optional[str]
    sheet_name: Optional[str]


class _CountingOutputRowSink(BaseRowSink):
    _sink: IRowSink
    _counter: _RowCounter

    def __init__(self, sink: IRowSink, counter: _RowCounter) -> None:
        self._sink = sink
        self._counter = counter

    @override
    def write_row(self, row: RowData) -> None:
        self._counter.rows += 1
        self._sink.write_row(row)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._counter.rows += len(rows)
        self._sink.write_batch(rows)

    @override
    def close(self) -> None:
        self._sink.close()


class RouterRowSink(BaseRowSink):
    """同一行数据流的多路输出路由器(流式).

    负责:
    - 分发与过滤
    - 失败策略
    - 按输出目标统计(行数/耗时/错误)
    - `close()` 时写入元信息/审计并保存工作簿容器
    """

    _routes: List[_RouteState]
    _failure_policy: str
    _workbook_resources: List[ExcelWorkbookSink]
    _meta_target: Optional[_FinalTargetState]
    _audit_target: Optional[_FinalTargetState]
    _emit_events: bool
    _instrumentation: Optional[InstrumentationHub]
    _input_rows: int
    _closed: bool
    _final_stats: List[OutputTargetStats]

    _demand_name: str
    _demand_main_source_id: str
    _demand_target_fields: List[str]
    _demand_field_fingerprints: List[Tuple[str, str, str, str]]
    _run_started_at_epoch: Optional[float]
    _run_parallel_mode: str
    _run_batch_size: Optional[int]
    _run_failure_policy: str

    def __init__(
        self,
        *,
        routes: Sequence[_RouteState],
        failure_policy: str,
        workbook_resources: Sequence[ExcelWorkbookSink],
        meta_target: Optional[_FinalTargetState] = None,
        audit_target: Optional[_FinalTargetState] = None,
        emit_events: bool = False,
        instrumentation: Optional[InstrumentationHub] = None,
        demand_name: str = "",
        demand_main_source_id: str = "",
        demand_target_fields: Optional[Sequence[str]] = None,
        demand_field_fingerprints: Optional[Sequence[Tuple[str, str, str, str]]] = None,
        run_started_at_epoch: Optional[float] = None,
        run_parallel_mode: str = "",
        run_batch_size: Optional[int] = None,
        run_failure_policy: str = "",
    ) -> None:
        self._routes = list(routes)
        self._failure_policy = str(failure_policy or "all_fail")
        self._workbook_resources = list(workbook_resources)
        self._meta_target = meta_target
        self._audit_target = audit_target
        self._emit_events = bool(emit_events)
        self._instrumentation = instrumentation
        self._input_rows = 0
        self._closed = False
        self._final_stats = []

        self._demand_name = str(demand_name or "")
        self._demand_main_source_id = str(demand_main_source_id or "")
        self._demand_target_fields = list(demand_target_fields or [])
        self._demand_field_fingerprints = list(demand_field_fingerprints or [])
        self._run_started_at_epoch = float(run_started_at_epoch) if run_started_at_epoch is not None else None
        self._run_parallel_mode = str(run_parallel_mode or "")
        self._run_batch_size = int(run_batch_size) if run_batch_size is not None else None
        self._run_failure_policy = str(run_failure_policy or "")

    def get_target_stats(self) -> List[OutputTargetStats]:
        stats: List[OutputTargetStats] = []
        for r in self._routes:
            output_rows = int(r.output_counter.rows) if r.output_counter is not None else int(r.input_row_count)
            error_type = type(r.first_error).__name__ if r.first_error is not None else None
            error_message = str(r.first_error) if r.first_error is not None else None
            stats.append(
                OutputTargetStats(
                    target_id=r.target_id,
                    input_row_count=int(r.input_row_count),
                    row_count=output_rows,
                    error_count=int(r.error_count),
                    duration_seconds=float(r.duration_seconds),
                    disabled=bool(r.disabled),
                    output_path=r.output_path,
                    sheet_name=r.sheet_name,
                    error_type=error_type,
                    error_message=error_message,
                )
            )
        stats.extend(list(self._final_stats))
        return stats

    @override
    def write_row(self, row: RowData) -> None:
        if self._closed:
            msg = "RouterRowSink is closed"
            raise RuntimeError(msg)
        self._input_rows += 1

        for route in self._routes:
            if route.disabled:
                continue
            if route.predicate is not None and not bool(route.predicate(row)):
                continue

            start = time.perf_counter()
            try:
                route.sink.write_row(row)
                route.input_row_count += 1
            except Exception as exc:
                route.error_count += 1
                if route.first_error is None:
                    route.first_error = exc
                if self._failure_policy == "primary_only" and not route.is_primary:
                    route.disabled = True
                    continue
                raise OutputTargetWriteError(route.target_id, exc) from exc
            finally:
                route.duration_seconds += time.perf_counter() - start

    def _close_route_sink(self, route: _RouteState) -> None:
        try:
            route.sink.close()
        except Exception as exc:
            route.error_count += 1
            if route.first_error is None:
                route.first_error = exc
            if self._failure_policy == "primary_only" and not route.is_primary:
                route.disabled = True
                return
            raise OutputTargetWriteError(route.target_id, exc) from exc

    @override
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        # 1) 关闭所有路由 `sink`(聚合器在此阶段 `finalize` 并写出)
        for route in self._routes:
            self._close_route_sink(route)

        # 2) 写入元信息/审计(必须在工作簿保存之前)
        self._write_meta_and_audit()

        # 3) 保存工作簿容器(原子替换)
        for wb in self._workbook_resources:
            wb.close()

        # 4) 输出级观测结束事件
        if self._emit_events and self._instrumentation is not None:
            for stat in self.get_target_stats():
                _ = self._instrumentation.emit(
                    EVENT_OUTPUT_TARGET_END,
                    OutputTargetEndEvent(
                        target_id=stat.target_id,
                        output_path=stat.output_path,
                        sheet_name=stat.sheet_name,
                        row_count=int(stat.row_count),
                        error_count=int(stat.error_count),
                        duration=float(stat.duration_seconds),
                        disabled=bool(stat.disabled),
                        error_type=stat.error_type,
                        error_message=stat.error_message,
                    ),
                )

    def _write_meta_and_audit(self) -> None:
        self._write_meta()
        self._write_audit()

    def _build_meta_rows(self) -> List[RowData]:
        rows: List[RowData] = []
        fingerprint = fingerprint_for_meta(
            demand_name=self._demand_name,
            main_source_id=self._demand_main_source_id,
            target_fields=self._demand_target_fields,
            field_specs=self._demand_field_fingerprints,
        )
        rows.append({"key": "demand.name", "value": self._demand_name})
        rows.append({"key": "demand.main_source_id", "value": self._demand_main_source_id})
        rows.append({"key": "demand.fingerprint", "value": fingerprint})
        rows.append({"key": "scalim.version", "value": str(SCALIM_VERSION)})
        rows.append({"key": "router.input_rows", "value": int(self._input_rows)})
        if self._run_started_at_epoch is not None:
            rows.append({"key": "run.started_at_epoch", "value": float(self._run_started_at_epoch)})
            rows.append({"key": "run.finished_at_epoch", "value": float(time.time())})
        if self._run_parallel_mode:
            rows.append({"key": "run.parallel_mode", "value": self._run_parallel_mode})
        if self._run_batch_size is not None:
            rows.append({"key": "run.batch_size", "value": int(self._run_batch_size)})
        if self._run_failure_policy:
            rows.append({"key": "run.failure_policy", "value": self._run_failure_policy})

        for stat in self.get_target_stats():
            prefix = "output.{}".format(stat.target_id)
            rows.append({"key": prefix + ".input_rows", "value": int(stat.input_row_count)})
            rows.append({"key": prefix + ".rows", "value": int(stat.row_count)})
            rows.append({"key": prefix + ".errors", "value": int(stat.error_count)})
            rows.append({"key": prefix + ".disabled", "value": bool(stat.disabled)})
            rows.append({"key": prefix + ".duration_seconds", "value": float(stat.duration_seconds)})
            if stat.sheet_name:
                rows.append({"key": prefix + ".sheet_name", "value": str(stat.sheet_name)})
            if stat.output_path:
                rows.append({"key": prefix + ".output_path", "value": str(stat.output_path)})
            if stat.error_type or stat.error_message:
                rows.append({"key": prefix + ".error_type", "value": stat.error_type or ""})
                rows.append({"key": prefix + ".error_message", "value": stat.error_message or ""})
        return rows

    def _write_meta(self) -> None:
        meta = self._meta_target
        if meta is None:
            return

        rows = self._build_meta_rows()
        meta.sink.write_batch(rows)
        meta.sink.close()
        self._final_stats.append(
            OutputTargetStats(
                target_id=meta.target_id,
                input_row_count=0,
                row_count=int(meta.output_counter.rows),
                error_count=0,
                duration_seconds=0.0,
                disabled=False,
                output_path=meta.output_path,
                sheet_name=meta.sheet_name,
            )
        )

    def _build_audit_rows(self) -> List[RowData]:
        rows: List[RowData] = []
        for stat in self.get_target_stats():
            if not stat.error_count:
                continue
            rows.append(
                {
                    "target_id": stat.target_id,
                    "error_type": stat.error_type,
                    "error_message": stat.error_message,
                    "error_count": int(stat.error_count),
                    "disabled": bool(stat.disabled),
                }
            )
        return rows

    def _write_audit(self) -> None:
        audit = self._audit_target
        if audit is None:
            return

        rows = self._build_audit_rows()
        if rows:
            audit.sink.write_batch(rows)
        audit.sink.close()
        self._final_stats.append(
            OutputTargetStats(
                target_id=audit.target_id,
                input_row_count=0,
                row_count=int(audit.output_counter.rows),
                error_count=0,
                duration_seconds=0.0,
                disabled=False,
                output_path=audit.output_path,
                sheet_name=audit.sheet_name,
            )
        )


@dataclass(frozen=True)
class OutputCompositionPlan:
    sink: RouterRowSink
    output_paths: Dict[str, str]


def _normalize_failure_policy(failure_policy: str) -> str:
    policy = str(failure_policy or "all_fail")
    if policy not in ("all_fail", "primary_only"):
        msg = "Unsupported failure_policy: {!r}".format(failure_policy)
        raise ValueError(msg)
    return policy


def _validate_excel_workbook_sheet_names(spec: OutputCompositionSpec) -> None:
    """确保同一路径的 `excel` 输出都显式声明 `sheet_name`(避免隐式覆盖)."""
    excel_paths: Dict[str, List[Tuple[str, Optional[str]]]] = {}

    def _collect_excel_path(target_id: str, output: OutputSpec, sheet_name: Optional[str]) -> None:
        fmt = (output.format or "csv").lower()
        if fmt == "excel" and output.path:
            excel_paths.setdefault(str(output.path), []).append((str(target_id), sheet_name))

    for t in spec.targets:
        _collect_excel_path(t.target_id, t.output, str(t.output.sheet_name) if t.output.sheet_name else None)
    for t in spec.derived_targets:
        _collect_excel_path(t.target_id, t.output, str(t.output.sheet_name) if t.output.sheet_name else None)
    if spec.meta_sheet is not None:
        _collect_excel_path(spec.meta_sheet.target_id, spec.meta_sheet.output, str(spec.meta_sheet.sheet_name))
    if spec.audit_sheet is not None:
        _collect_excel_path(spec.audit_sheet.target_id, spec.audit_sheet.output, str(spec.audit_sheet.sheet_name))

    for path, entries in excel_paths.items():
        if len(entries) <= 1:
            continue
        missing = [tid for tid, sheet in entries if not sheet]
        if missing:
            msg = (
                "Excel workbook path is shared by multiple outputs, but some outputs are missing sheet_name: path={!r}, targets={}"
            ).format(path, ", ".join(sorted(missing)))
            raise ValueError(msg)


def _create_row_sink_for_composed_output(
    *,
    target_id: str,
    output: OutputSpec,
    layout: ExportLayout,
    workbook_by_path: Dict[str, ExcelWorkbookSink],
) -> Tuple[IRowSink, _RowCounter]:
    fmt = (output.format or "csv").lower()
    if not output.path:
        msg = "OutputSpec.path is required for composed outputs (target_id={}, format={})".format(target_id, fmt)
        raise ValueError(msg)

    if fmt == "csv":
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for csv (streaming=true)"
            raise ValueError(msg)
        counter = _RowCounter()
        sink = _CountingOutputRowSink(_create_csv_sink(output, layout), counter)
        return sink, counter

    if fmt == "excel":
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for excel (streaming=true)"
            raise ValueError(msg)

        counter = _RowCounter()
        if output.sheet_name:
            path = str(output.path)
            wb = workbook_by_path.get(path)
            if wb is None:
                wb = ExcelWorkbookSink(path)
                workbook_by_path[path] = wb
            field_names = list(layout.field_ids)
            header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
            sheet_sink = wb.create_sheet_row_sink(
                str(output.sheet_name),
                field_names=field_names,
                header_names=header_names,
                include_header=bool(output.include_header),
            )
            sink = _CountingOutputRowSink(sheet_sink, counter)
            return sink, counter

        # 单工作表 `Excel` 输出(独立文件)
        sink = _CountingOutputRowSink(_create_excel_row_sink(output, layout), counter)
        return sink, counter

    msg = "Unsupported output format for composed outputs: {!r}".format(output.format)
    raise ValueError(msg)


def _append_route_state(
    *,
    routes: List[_RouteState],
    output_paths: Dict[str, str],
    target_id: str,
    sink: IRowSink,
    predicate: Optional[OutputRowPredicate],
    is_primary: bool,
    output: OutputSpec,
    output_counter: _RowCounter,
) -> None:
    output_paths[str(target_id)] = str(output.path) if output.path else ""
    routes.append(
        _RouteState(
            target_id=str(target_id),
            sink=sink,
            predicate=predicate,
            is_primary=bool(is_primary),
            output_path=str(output.path) if output.path else None,
            sheet_name=str(output.sheet_name) if output.sheet_name else None,
            output_counter=output_counter,
        )
    )


def _append_direct_target_routes(
    *,
    routes: List[_RouteState],
    output_paths: Dict[str, str],
    targets: Sequence[OutputTargetSpec],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
) -> None:
    for t in targets:
        sink, counter = _create_row_sink_for_composed_output(
            target_id=str(t.target_id),
            output=t.output,
            layout=t.layout,
            workbook_by_path=workbook_by_path,
        )
        _append_route_state(
            routes=routes,
            output_paths=output_paths,
            target_id=str(t.target_id),
            sink=sink,
            predicate=t.predicate,
            is_primary=bool(t.is_primary),
            output=t.output,
            output_counter=counter,
        )


def _append_derived_target_routes(
    *,
    routes: List[_RouteState],
    output_paths: Dict[str, str],
    targets: Sequence[DerivedOutputTargetSpec],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
) -> None:
    for t in targets:
        out_sink, out_counter = _create_row_sink_for_composed_output(
            target_id=str(t.target_id),
            output=t.output,
            layout=t.output_layout,
            workbook_by_path=workbook_by_path,
        )
        if t.derived.rank_by:
            agg = RankedGroupByAggregator(
                group_by=t.derived.group_by,
                metrics=t.derived.metrics,
                rank_by=str(t.derived.rank_by),
                rank_field_id=str(t.derived.rank_field_id),
                order=str(t.derived.rank_order),
                top_k=int(t.derived.top_k),
                max_groups=int(t.derived.max_groups),
            )
        else:
            agg = GroupByAggregator(group_by=t.derived.group_by, metrics=t.derived.metrics, max_groups=int(t.derived.max_groups))

        sink = AggregatingRowSink(aggregator=agg, out_sink=out_sink)
        _append_route_state(
            routes=routes,
            output_paths=output_paths,
            target_id=str(t.target_id),
            sink=sink,
            predicate=None,
            is_primary=bool(t.is_primary),
            output=t.output,
            output_counter=out_counter,
        )


def _ensure_primary_route(routes: List[_RouteState]) -> None:
    if routes and not any(r.is_primary for r in routes):
        routes[0].is_primary = True


def _maybe_create_meta_target(
    *,
    meta_sheet: Optional[MetaSheetSpec],
    output_paths: Dict[str, str],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
) -> Optional[_FinalTargetState]:
    if meta_sheet is None:
        return None

    layout = ExportLayout(field_ids=("key", "value"), header_names=("key", "value"))
    meta_output = OutputSpec(
        format=meta_sheet.output.format,
        path=meta_sheet.output.path,
        encoding=meta_sheet.output.encoding,
        streaming=True,
        include_header=True,
        sheet_name=str(meta_sheet.sheet_name),
    )
    sink, counter = _create_row_sink_for_composed_output(
        target_id=str(meta_sheet.target_id),
        output=meta_output,
        layout=layout,
        workbook_by_path=workbook_by_path,
    )
    output_paths[str(meta_sheet.target_id)] = str(meta_output.path) if meta_output.path else ""
    return _FinalTargetState(
        target_id=str(meta_sheet.target_id),
        sink=sink,
        output_counter=counter,
        output_path=str(meta_output.path) if meta_output.path else None,
        sheet_name=str(meta_output.sheet_name) if meta_output.sheet_name else None,
    )


def _maybe_create_audit_target(
    *,
    audit_sheet: Optional[AuditSheetSpec],
    output_paths: Dict[str, str],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
) -> Optional[_FinalTargetState]:
    if audit_sheet is None:
        return None

    layout = ExportLayout(
        field_ids=("target_id", "error_type", "error_message", "error_count", "disabled"),
        header_names=("target_id", "error_type", "error_message", "error_count", "disabled"),
    )
    audit_output = OutputSpec(
        format=audit_sheet.output.format,
        path=audit_sheet.output.path,
        encoding=audit_sheet.output.encoding,
        streaming=True,
        include_header=True,
        sheet_name=str(audit_sheet.sheet_name),
    )
    sink, counter = _create_row_sink_for_composed_output(
        target_id=str(audit_sheet.target_id),
        output=audit_output,
        layout=layout,
        workbook_by_path=workbook_by_path,
    )
    output_paths[str(audit_sheet.target_id)] = str(audit_output.path) if audit_output.path else ""
    return _FinalTargetState(
        target_id=str(audit_sheet.target_id),
        sink=sink,
        output_counter=counter,
        output_path=str(audit_output.path) if audit_output.path else None,
        sheet_name=str(audit_output.sheet_name) if audit_output.sheet_name else None,
    )


def build_output_composition(
    *,
    spec: OutputCompositionSpec,
    demand_name: str,
    demand_main_source_id: str,
    demand_target_fields: Sequence[str],
    demand_field_fingerprints: Sequence[Tuple[str, str, str, str]],
    run_started_at_epoch: Optional[float] = None,
    run_parallel_mode: str = "",
    run_batch_size: Optional[int] = None,
    instrumentation: Optional[InstrumentationHub] = None,
) -> OutputCompositionPlan:
    """物化多输出组合为一个 `IRowSink`(`RouterRowSink`).

    该函数只处理行流式写出路径.
    """

    failure_policy = _normalize_failure_policy(spec.failure_policy)
    _validate_excel_workbook_sheet_names(spec)

    workbook_by_path: Dict[str, ExcelWorkbookSink] = {}
    output_paths: Dict[str, str] = {}

    routes: List[_RouteState] = []

    _append_direct_target_routes(
        routes=routes,
        output_paths=output_paths,
        targets=spec.targets,
        workbook_by_path=workbook_by_path,
    )
    _append_derived_target_routes(
        routes=routes,
        output_paths=output_paths,
        targets=spec.derived_targets,
        workbook_by_path=workbook_by_path,
    )
    _ensure_primary_route(routes)

    meta_target = _maybe_create_meta_target(
        meta_sheet=spec.meta_sheet,
        output_paths=output_paths,
        workbook_by_path=workbook_by_path,
    )
    audit_target = _maybe_create_audit_target(
        audit_sheet=spec.audit_sheet,
        output_paths=output_paths,
        workbook_by_path=workbook_by_path,
    )

    # 构建路由器
    wb_resources = list(workbook_by_path.values())
    router = RouterRowSink(
        routes=routes,
        failure_policy=failure_policy,
        workbook_resources=wb_resources,
        meta_target=meta_target,
        audit_target=audit_target,
        emit_events=True,
        instrumentation=instrumentation,
        demand_name=demand_name,
        demand_main_source_id=demand_main_source_id,
        demand_target_fields=list(demand_target_fields),
        demand_field_fingerprints=list(demand_field_fingerprints),
        run_started_at_epoch=run_started_at_epoch,
        run_parallel_mode=run_parallel_mode,
        run_batch_size=run_batch_size,
        run_failure_policy=failure_policy,
    )

    return OutputCompositionPlan(
        sink=router,
        output_paths={k: v for k, v in output_paths.items() if v},
    )


__all__ = [
    "AuditSheetSpec",
    "DerivedGroupBySpec",
    "DerivedOutputTargetSpec",
    "MetaSheetSpec",
    "OutputCompositionPlan",
    "OutputCompositionSpec",
    "OutputTargetSpec",
    "OutputTargetStats",
    "OutputTargetWriteError",
    "RouterRowSink",
    "build_output_composition",
    "required_demand_fields",
]
