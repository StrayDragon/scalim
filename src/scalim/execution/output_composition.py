from __future__ import absolute_import

import hashlib
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .._internal.loggingx import format_kv, get_logger, prefix
from .._project_constants import VERSION as SCALIM_VERSION
from ..events.catalog import EVENT_OUTPUT_TARGET_END
from ..events.events import OutputTargetEndEvent
from ..exceptions import ScalimExecutionError
from ..ob.hub import InstrumentationHub
from ..sinks.sink_base import BaseRowSink, IRowSink
from ..sinks.sink_csv import CSVSink, InMemoryCsvSink
from ..typedefs import KeyNormalizationMode, RowData
from ..utils.iterables import ordered_unique_str
from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import dataclass
from .derived_outputs import (
    AggMetricSpec,
    AggregatingRowSink,
    DedupByThenAggregator,
    GroupByAggregator,
    IRowAggregator,
    PostFieldSpec,
    RankedGroupByAggregator,
    RankFieldSpec,
    TwoStageGroupByAggregator,
    build_finalize_dag_plan,
    fingerprint_for_meta,
)
from .output_contracts import ExportLayout, OutputSpec

OutputRowPredicate = Callable[[RowData], bool]

_logger = get_logger("derived_outputs")

if TYPE_CHECKING:
    from ..sinks.sink_excel import ExcelWorkbookSink


@dataclass(frozen=True)
class OutputTargetSpec:
    """输出目标(`IR/Python-only`).

    - `layout.field_ids` 表示该目标写出的字段顺序(来自输入行 `dict` 取值).
    - `output.sheet_name` 仅在 `excel` 且写入同一工作簿容器时使用.
    """

    target_id: str
    layout: ExportLayout
    output: OutputSpec
    in_memory: bool = False
    predicate: Optional[OutputRowPredicate] = None
    is_primary: bool = False
    requires: Optional[Tuple[str, ...]] = None


class IDerivedAggregationSpec(ABC):
    @abstractmethod
    def required_fields(self) -> Tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def fingerprint_parts(self) -> Tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        raise NotImplementedError


def _metric_fingerprint_part(m: AggMetricSpec) -> str:
    field_id = str(m.field_id) if m.field_id else ""
    field_ids = ",".join(str(x) for x in (m.field_ids or ()))
    threshold = "" if m.threshold is None else str(m.threshold)
    return "{}|op={}|field_id={}|field_ids={}|threshold={}".format(str(m.out_field_id), str(m.op), field_id, field_ids, threshold)


def _rank_field_fingerprint_part(r: RankFieldSpec) -> str:
    return "{}|kind={}|by={}|partition_by={}|order={}|order_by={}|top_k={}|top_k_mode={}".format(
        str(r.out_field_id),
        str(r.kind),
        str(r.by),
        ",".join(str(x) for x in (r.partition_by or ())),
        str(r.order),
        ",".join(str(x) for x in (r.order_by or ())),
        int(r.top_k),
        str(r.top_k_mode),
    )


def _post_field_fingerprint_part(p: PostFieldSpec) -> str:
    return "{}|kind={}|deps={}|fingerprint={}".format(
        str(p.out_field_id),
        str(p.kind),
        ",".join(str(x) for x in (p.dependencies or ())),
        str(p.fingerprint),
    )


@dataclass(frozen=True)
class DerivedGroupBySpec(IDerivedAggregationSpec):
    """派生汇总输出(内置 `group_by`)."""

    group_by: Tuple[str, ...]
    metrics: Tuple[AggMetricSpec, ...]
    rank_fields: Tuple[RankFieldSpec, ...] = ()
    post_fields: Tuple[PostFieldSpec, ...] = ()
    max_groups: int = 0
    max_distinct: int = 0
    distinct_on_overflow: str = "error"

    @override
    def required_fields(self) -> Tuple[str, ...]:
        agg = GroupByAggregator(group_by=self.group_by, metrics=self.metrics, max_groups=0)
        return agg.required_fields()

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = []
        parts.append("kind=group_by")
        parts.append("group_by=" + ",".join(str(x) for x in self.group_by))
        parts.append("max_groups=" + str(int(self.max_groups)))
        parts.append("max_distinct=" + str(int(self.max_distinct)))
        parts.append("distinct_on_overflow=" + str(self.distinct_on_overflow or "error").lower())
        parts.append("metrics=")
        for m in self.metrics:
            parts.append("  " + _metric_fingerprint_part(m))
        parts.append("rank_fields=")
        for r in sorted(self.rank_fields, key=lambda x: str(x.out_field_id)):
            parts.append("  " + _rank_field_fingerprint_part(r))
        parts.append("post_fields=")
        for p in sorted(self.post_fields, key=lambda x: str(x.out_field_id)):
            parts.append("  " + _post_field_fingerprint_part(p))
        parts.append("finalize_dag_plan=")
        plan = build_finalize_dag_plan(rank_fields=self.rank_fields, post_fields=self.post_fields)
        for item in plan.items:
            deps = ",".join(str(x) for x in (item.dependencies or ()))
            parts.append(
                "  {}|producer_key={}|phase={}|deps={}".format(
                    str(item.out_field_id),
                    str(item.producer_key),
                    str(item.phase),
                    deps,
                )
            )
        return tuple(parts)

    @override
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        _ = str(parallel_mode or "").lower()
        overflow = str(self.distinct_on_overflow or "error").lower()
        if overflow not in ("error", "truncate"):
            msg = "Unsupported distinct_on_overflow: {!r}".format(self.distinct_on_overflow)
            raise ValueError(msg)

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        if self.rank_fields or self.post_fields:
            return RankedGroupByAggregator(
                group_by=self.group_by,
                metrics=self.metrics,
                rank_fields=self.rank_fields,
                post_fields=self.post_fields,
                max_groups=int(self.max_groups),
                max_distinct=int(self.max_distinct),
                distinct_on_overflow=str(self.distinct_on_overflow),
                key_normalization=key_normalization,
            )
        return GroupByAggregator(
            group_by=self.group_by,
            metrics=self.metrics,
            max_groups=int(self.max_groups),
            max_distinct=int(self.max_distinct),
            distinct_on_overflow=str(self.distinct_on_overflow),
            key_normalization=key_normalization,
        )


@dataclass(frozen=True)
class DedupBySpec:
    key_fields: Tuple[str, ...]
    on_conflict: str = "error"
    max_distinct: int = 0
    on_overflow: str = "error"

    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = []
        parts.append("kind=dedup_by")
        parts.append("key_fields=" + ",".join(str(x) for x in self.key_fields))
        parts.append("on_conflict=" + str(self.on_conflict or "error").lower())
        parts.append("max_distinct=" + str(int(self.max_distinct)))
        parts.append("on_overflow=" + str(self.on_overflow or "error").lower())
        return tuple(parts)

    def validate_parallel_mode(self, parallel_mode: str) -> None:
        mode = str(parallel_mode or "").lower()
        on_conflict = str(self.on_conflict or "error").lower()
        if on_conflict not in ("error", "first", "last"):
            msg = "Unsupported dedup_by.on_conflict: {!r}".format(self.on_conflict)
            raise ValueError(msg)
        on_overflow = str(self.on_overflow or "error").lower()
        if on_overflow not in ("error", "truncate"):
            msg = "Unsupported dedup_by.on_overflow: {!r}".format(self.on_overflow)
            raise ValueError(msg)
        if mode == "adaptive" and on_conflict in ("first", "last"):
            msg = (
                "dedup_by.on_conflict={!r} is order-dependent and is not supported in parallel_mode='adaptive'; "
                "use parallel_mode='seq' or switch to on_conflict='error'"
            ).format(on_conflict)
            raise ValueError(msg)


@dataclass(frozen=True)
class DerivedDedupByGroupBySpec(IDerivedAggregationSpec):
    dedup_by: DedupBySpec
    group_by: DerivedGroupBySpec

    @override
    def required_fields(self) -> Tuple[str, ...]:
        required: List[str] = list(self.dedup_by.key_fields) + list(self.group_by.required_fields())
        # 去重但保留顺序.
        seen: Set[str] = set()
        ordered: List[str] = []
        for fid in required:
            if fid in seen:
                continue
            seen.add(fid)
            ordered.append(fid)
        return tuple(ordered)

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = ["kind=dedup_by+group_by", "dedup_by:"]
        parts.extend(["  " + x for x in self.dedup_by.fingerprint_parts()])
        parts.append("group_by:")
        parts.extend(["  " + x for x in self.group_by.fingerprint_parts()])
        return tuple(parts)

    @override
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        self.dedup_by.validate_parallel_mode(parallel_mode)
        self.group_by.validate_parallel_mode(parallel_mode)

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        base = self.group_by.build_aggregator(key_normalization=key_normalization)
        return DedupByThenAggregator(
            key_fields=self.dedup_by.key_fields,
            on_conflict=str(self.dedup_by.on_conflict),
            max_distinct=int(self.dedup_by.max_distinct),
            on_overflow=str(self.dedup_by.on_overflow),
            downstream=base,
            key_normalization=key_normalization,
        )


@dataclass(frozen=True)
class TwoStageGroupBySpec(IDerivedAggregationSpec):
    stage1: DerivedGroupBySpec
    stage2: DerivedGroupBySpec

    @override
    def required_fields(self) -> Tuple[str, ...]:
        return self.stage1.required_fields()

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = ["kind=two_stage_group_by", "stage1:"]
        parts.extend(["  " + x for x in self.stage1.fingerprint_parts()])
        parts.append("stage2:")
        parts.extend(["  " + x for x in self.stage2.fingerprint_parts()])
        return tuple(parts)

    @override
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        if self.stage1.rank_fields or self.stage1.post_fields or self.stage2.rank_fields or self.stage2.post_fields:
            msg = "two_stage_group_by does not support rank/post fields in stage specs"
            raise ValueError(msg)
        self.stage1.validate_parallel_mode(parallel_mode)
        self.stage2.validate_parallel_mode(parallel_mode)

        stage1_fields: Set[str] = set(self.stage1.group_by)
        stage1_fields.update([str(m.out_field_id) for m in self.stage1.metrics])
        missing = [x for x in self.stage2.required_fields() if x not in stage1_fields]
        if missing:
            msg = "two_stage_group_by stage2 requires fields not produced by stage1: {}".format(", ".join(sorted(missing)))
            raise ValueError(msg)

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        agg1 = GroupByAggregator(
            group_by=self.stage1.group_by,
            metrics=self.stage1.metrics,
            max_groups=int(self.stage1.max_groups),
            max_distinct=int(self.stage1.max_distinct),
            distinct_on_overflow=str(self.stage1.distinct_on_overflow),
            key_normalization=key_normalization,
        )
        agg2 = GroupByAggregator(
            group_by=self.stage2.group_by,
            metrics=self.stage2.metrics,
            max_groups=int(self.stage2.max_groups),
            max_distinct=int(self.stage2.max_distinct),
            distinct_on_overflow=str(self.stage2.distinct_on_overflow),
            key_normalization=key_normalization,
        )
        return TwoStageGroupByAggregator(stage1=agg1, stage2=agg2)


@dataclass(frozen=True)
class DerivedOutputTargetSpec:
    """派生输出目标: 从明细流聚合并在 `close()` 时输出."""

    target_id: str
    derived: IDerivedAggregationSpec
    output_layout: ExportLayout
    output: OutputSpec
    in_memory: bool = False
    predicate: Optional[OutputRowPredicate] = None
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
    include_full_error_message: bool = False


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
    error_message_hash: Optional[str] = None


class ScalimOutputTargetWriteError(ScalimExecutionError):
    target_id: str

    def __init__(self, target_id: str, exc: Exception) -> None:
        super(ScalimOutputTargetWriteError, self).__init__("Output target failed: {}: {}".format(target_id, exc))
        self.target_id = str(target_id)


def _sha256_text(value: str) -> str:
    digest = hashlib.sha256()
    digest.update(value.encode("utf-8", errors="replace"))
    return digest.hexdigest()


def _fingerprint_for_derived_target(*, target_id: str, derived: IDerivedAggregationSpec) -> str:
    h = hashlib.sha1()  # noqa: S324
    payload = "\n".join(["target_id=" + str(target_id), *derived.fingerprint_parts()]).encode("utf-8", errors="replace")
    h.update(payload)
    return h.hexdigest()


def _as_single_line(value: str) -> str:
    # 避免 `meta/audit` 出现多行单元格,并保持输出可预测.
    return " ".join(str(value).splitlines())


def _truncate_text(value: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "…(truncated)"


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
    return ordered_unique_str(fields)


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


def _create_in_memory_csv_sink(layout: ExportLayout) -> InMemoryCsvSink:
    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
    return InMemoryCsvSink(field_names=field_names, header_names=header_names)


def _create_excel_row_sink(output: OutputSpec, layout: ExportLayout) -> IRowSink:
    from ..sinks.sink_excel import ExcelSink  # noqa: PLC0415

    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
    sheet_name = str(output.sheet_name) if output.sheet_name else "Sheet1"
    return ExcelSink(
        output_path=str(output.path),
        field_names=field_names,
        header_names=header_names,
        sheet_name=sheet_name,
        include_header=bool(output.include_header),
        allow_formulas=bool(output.excel_allow_formulas),
        write_lock=bool(output.write_lock),
    )


@dataclass
class _RouteState:
    target_id: str
    sink: IRowSink
    predicate: Optional[OutputRowPredicate]
    is_primary: bool
    output_path: Optional[str]
    sheet_name: Optional[str]
    derived_fingerprint: Optional[str] = None
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
    _workbook_resources: List["ExcelWorkbookSink"]
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
    _include_full_error_message: bool

    def __init__(
        self,
        *,
        routes: Sequence[_RouteState],
        failure_policy: str,
        workbook_resources: Sequence["ExcelWorkbookSink"],
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
        include_full_error_message: bool = False,
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
        self._include_full_error_message = bool(include_full_error_message)

    def get_target_stats(self) -> List[OutputTargetStats]:
        stats: List[OutputTargetStats] = []
        for r in self._routes:
            output_rows = int(r.output_counter.rows) if r.output_counter is not None else int(r.input_row_count)
            error_type = type(r.first_error).__name__ if r.first_error is not None else None
            error_message = None
            error_message_hash = None
            if r.first_error is not None:
                raw = str(r.first_error)
                error_message_hash = _sha256_text(raw)
                if self._include_full_error_message:
                    normalized = _as_single_line(raw)
                    error_message = _truncate_text(normalized, max_chars=2000)
                else:
                    # 默认使用脱敏摘要,避免把敏感信息落到输出文件中.
                    error_message = "sha256={}".format(error_message_hash)
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
                    error_message_hash=error_message_hash,
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
                raise ScalimOutputTargetWriteError(route.target_id, exc) from exc
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
            raise ScalimOutputTargetWriteError(route.target_id, exc) from exc

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

    def _append_output_stats_meta_rows(self, rows: List[RowData]) -> None:
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
            if stat.error_type or stat.error_message or stat.error_message_hash:
                rows.append({"key": prefix + ".error_type", "value": stat.error_type or ""})
                rows.append({"key": prefix + ".error_message", "value": stat.error_message or ""})
                if stat.error_message_hash:
                    rows.append({"key": prefix + ".error_message_hash", "value": str(stat.error_message_hash)})

    def _append_derived_meta_rows(self, rows: List[RowData]) -> None:
        # 派生聚合指纹与诊断(仅包含对拍友好的脱敏信息)
        for route in self._routes:
            if route.derived_fingerprint:
                rows.append({"key": "derived.{}.fingerprint".format(route.target_id), "value": str(route.derived_fingerprint)})
            if not isinstance(route.sink, AggregatingRowSink):
                continue
            diag = route.sink.aggregator.diagnostics()
            for k, v in diag.meta.items():
                rows.append({"key": "derived.{}.{}".format(route.target_id, str(k)), "value": v})

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

        self._append_output_stats_meta_rows(rows)
        self._append_derived_meta_rows(rows)
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
        route_by_id = {r.target_id: r for r in self._routes}

        for stat in self.get_target_stats():
            if not stat.error_count:
                continue
            fingerprint = ""
            route = route_by_id.get(stat.target_id)
            if route is not None and route.derived_fingerprint:
                fingerprint = str(route.derived_fingerprint)
            rows.append(
                {
                    "target_id": stat.target_id,
                    "event_type": "output_error",
                    "fingerprint": fingerprint,
                    "error_type": stat.error_type,
                    "error_message": stat.error_message,
                    "error_message_hash": stat.error_message_hash,
                    "error_count": int(stat.error_count),
                    "disabled": bool(stat.disabled),
                }
            )

        for route in self._routes:
            if not isinstance(route.sink, AggregatingRowSink):
                continue
            diag = route.sink.aggregator.diagnostics()
            for event in diag.audit_events:
                raw = str(event.get("message") or "")
                event_type = str(event.get("event_type") or "derived_event")
                msg_hash = _sha256_text(raw)
                if self._include_full_error_message:
                    normalized = _as_single_line(raw)
                    msg_out = _truncate_text(normalized, max_chars=2000)
                else:
                    msg_out = "sha256={}".format(msg_hash)
                rows.append(
                    {
                        "target_id": route.target_id,
                        "event_type": event_type,
                        "fingerprint": str(route.derived_fingerprint or ""),
                        "error_type": event_type,
                        "error_message": msg_out,
                        "error_message_hash": msg_hash,
                        "error_count": 0,
                        "disabled": bool(route.disabled),
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
    in_memory_csv_sinks: Dict[str, InMemoryCsvSink]


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


def _get_or_create_excel_workbook_sink(
    output: OutputSpec,
    *,
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
) -> "ExcelWorkbookSink":
    from ..sinks.sink_excel import ExcelWorkbookSink  # noqa: PLC0415

    path = str(output.path)
    wb = workbook_by_path.get(path)
    if wb is None:
        wb = ExcelWorkbookSink(path, write_lock=bool(output.write_lock))
        workbook_by_path[path] = wb
    else:
        wb.write_lock = bool(wb.write_lock or output.write_lock)
    return wb


def _create_row_sink_for_composed_output(
    *,
    target_id: str,
    output: OutputSpec,
    layout: ExportLayout,
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
    in_memory: bool = False,
) -> Tuple[IRowSink, _RowCounter, Optional[InMemoryCsvSink]]:
    fmt = (output.format or "csv").lower()
    if not output.path and not in_memory:
        msg = "OutputSpec.path is required for composed outputs (target_id={}, format={})".format(target_id, fmt)
        raise ValueError(msg)

    if in_memory:
        if fmt != "csv":
            msg = "In-memory composed output only supports format=csv (target_id={}, format={})".format(target_id, fmt)
            raise ValueError(msg)
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for csv (streaming=true)"
            raise ValueError(msg)
        counter = _RowCounter()
        mem_sink = _create_in_memory_csv_sink(layout)
        sink = _CountingOutputRowSink(mem_sink, counter)
        return sink, counter, mem_sink

    if fmt == "csv":
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for csv (streaming=true)"
            raise ValueError(msg)
        counter = _RowCounter()
        sink = _CountingOutputRowSink(_create_csv_sink(output, layout), counter)
        return sink, counter, None

    if fmt == "excel":
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for excel (streaming=true)"
            raise ValueError(msg)

        counter = _RowCounter()
        if output.sheet_name:
            wb = _get_or_create_excel_workbook_sink(output, workbook_by_path=workbook_by_path)
            field_names = list(layout.field_ids)
            header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
            sheet_sink = wb.create_sheet_row_sink(
                str(output.sheet_name),
                field_names=field_names,
                header_names=header_names,
                include_header=bool(output.include_header),
                allow_formulas=bool(output.excel_allow_formulas),
            )
            sink = _CountingOutputRowSink(sheet_sink, counter)
            return sink, counter, None

        # 单工作表 `Excel` 输出(独立文件)
        sink = _CountingOutputRowSink(_create_excel_row_sink(output, layout), counter)
        return sink, counter, None

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
    derived_fingerprint: Optional[str] = None,
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
            derived_fingerprint=str(derived_fingerprint) if derived_fingerprint else None,
            output_counter=output_counter,
        )
    )


def _append_direct_target_routes(
    *,
    routes: List[_RouteState],
    output_paths: Dict[str, str],
    in_memory_csv_sinks: Dict[str, InMemoryCsvSink],
    targets: Sequence[OutputTargetSpec],
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
) -> None:
    for t in targets:
        sink, counter, mem_sink = _create_row_sink_for_composed_output(
            target_id=str(t.target_id),
            output=t.output,
            layout=t.layout,
            workbook_by_path=workbook_by_path,
            in_memory=bool(t.in_memory),
        )
        if mem_sink is not None:
            in_memory_csv_sinks[str(t.target_id)] = mem_sink
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


def _validate_derived_parallel_mode(target_id: str, derived: IDerivedAggregationSpec, run_parallel_mode: str) -> None:
    try:
        derived.validate_parallel_mode(run_parallel_mode)
    except ValueError as exc:
        msg = "派生输出不支持 parallel_mode={!r}: target_id={!r}: {}".format(str(run_parallel_mode), str(target_id), exc)
        raise ValueError(msg) from exc


def _collect_specs_for_derived_warnings(derived: IDerivedAggregationSpec) -> Tuple[List[DerivedGroupBySpec], List[DedupBySpec]]:
    if isinstance(derived, DerivedGroupBySpec):
        return [derived], []
    if isinstance(derived, DerivedDedupByGroupBySpec):
        return [derived.group_by], [derived.dedup_by]
    if isinstance(derived, TwoStageGroupBySpec):
        return [derived.stage1, derived.stage2], []
    return [], []


def _warn_derived_guardrails(*, target_id: str, group_specs: Sequence[DerivedGroupBySpec], dedup_specs: Sequence[DedupBySpec]) -> None:
    for g in group_specs:
        if not int(g.max_groups):
            kv = format_kv(target_id=target_id, group_by=g.group_by)
            _logger.warning(
                "%smax_groups=0(不设上限), 高基数分组可能耗尽内存; 建议设置 max_groups %s",
                prefix("derived_outputs"),
                kv,
            )
        has_count_distinct = any(str(m.op).lower() == "count_distinct" for m in g.metrics)
        if has_count_distinct and not int(g.max_distinct):
            kv = format_kv(target_id=target_id, group_by=g.group_by)
            _logger.warning(
                "%smax_distinct=0(不设上限), count_distinct 高基数可能耗尽内存; 建议设置 max_distinct %s",
                prefix("derived_outputs"),
                kv,
            )

    for d in dedup_specs:
        if not int(d.max_distinct):
            kv = format_kv(target_id=target_id, key_fields=d.key_fields)
            _logger.warning(
                "%sdedup_by.max_distinct=0(不设上限), 高基数去重可能耗尽内存; 建议设置 dedup_by.max_distinct %s",
                prefix("derived_outputs"),
                kv,
            )


def _append_derived_target_routes(
    *,
    routes: List[_RouteState],
    output_paths: Dict[str, str],
    in_memory_csv_sinks: Dict[str, InMemoryCsvSink],
    targets: Sequence[DerivedOutputTargetSpec],
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
    run_parallel_mode: str,
    run_key_normalization: KeyNormalizationMode,
) -> None:
    for t in targets:
        # `adaptive` 下的确定性边界 `fail-fast` 校验
        _validate_derived_parallel_mode(str(t.target_id), t.derived, run_parallel_mode)
        derived_fingerprint = _fingerprint_for_derived_target(target_id=str(t.target_id), derived=t.derived)
        group_specs, dedup_specs = _collect_specs_for_derived_warnings(t.derived)
        _warn_derived_guardrails(target_id=str(t.target_id), group_specs=group_specs, dedup_specs=dedup_specs)

        out_sink, out_counter, mem_sink = _create_row_sink_for_composed_output(
            target_id=str(t.target_id),
            output=t.output,
            layout=t.output_layout,
            workbook_by_path=workbook_by_path,
            in_memory=bool(t.in_memory),
        )
        if mem_sink is not None:
            in_memory_csv_sinks[str(t.target_id)] = mem_sink
        agg = t.derived.build_aggregator(key_normalization=run_key_normalization)

        sink = AggregatingRowSink(aggregator=agg, out_sink=out_sink)
        _append_route_state(
            routes=routes,
            output_paths=output_paths,
            target_id=str(t.target_id),
            sink=sink,
            predicate=t.predicate,
            is_primary=bool(t.is_primary),
            output=t.output,
            output_counter=out_counter,
            derived_fingerprint=derived_fingerprint,
        )


def _ensure_primary_route(routes: List[_RouteState]) -> None:
    if routes and not any(r.is_primary for r in routes):
        routes[0].is_primary = True


def _maybe_create_meta_target(
    *,
    meta_sheet: Optional[MetaSheetSpec],
    output_paths: Dict[str, str],
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
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
        excel_allow_formulas=bool(meta_sheet.output.excel_allow_formulas),
        write_lock=bool(meta_sheet.output.write_lock),
    )
    sink, counter, _ = _create_row_sink_for_composed_output(
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
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
) -> Optional[_FinalTargetState]:
    if audit_sheet is None:
        return None

    layout = ExportLayout(
        field_ids=(
            "target_id",
            "error_type",
            "error_message",
            "error_count",
            "disabled",
            "event_type",
            "fingerprint",
            "error_message_hash",
        ),
        header_names=(
            "target_id",
            "error_type",
            "error_message",
            "error_count",
            "disabled",
            "event_type",
            "fingerprint",
            "error_message_hash",
        ),
    )
    audit_output = OutputSpec(
        format=audit_sheet.output.format,
        path=audit_sheet.output.path,
        encoding=audit_sheet.output.encoding,
        streaming=True,
        include_header=True,
        sheet_name=str(audit_sheet.sheet_name),
        excel_allow_formulas=bool(audit_sheet.output.excel_allow_formulas),
        write_lock=bool(audit_sheet.output.write_lock),
    )
    sink, counter, _ = _create_row_sink_for_composed_output(
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
    run_key_normalization: KeyNormalizationMode = "raw",
    instrumentation: Optional[InstrumentationHub] = None,
) -> OutputCompositionPlan:
    """物化多输出组合为一个 `IRowSink`(`RouterRowSink`).

    该函数只处理行流式写出路径.
    """

    failure_policy = _normalize_failure_policy(spec.failure_policy)
    _validate_excel_workbook_sheet_names(spec)

    workbook_by_path: Dict[str, "ExcelWorkbookSink"] = {}
    output_paths: Dict[str, str] = {}
    in_memory_csv_sinks: Dict[str, InMemoryCsvSink] = {}

    routes: List[_RouteState] = []

    _append_direct_target_routes(
        routes=routes,
        output_paths=output_paths,
        in_memory_csv_sinks=in_memory_csv_sinks,
        targets=spec.targets,
        workbook_by_path=workbook_by_path,
    )
    _append_derived_target_routes(
        routes=routes,
        output_paths=output_paths,
        in_memory_csv_sinks=in_memory_csv_sinks,
        targets=spec.derived_targets,
        workbook_by_path=workbook_by_path,
        run_parallel_mode=str(run_parallel_mode or ""),
        run_key_normalization=run_key_normalization,
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
        include_full_error_message=bool(spec.include_full_error_message),
    )

    return OutputCompositionPlan(
        sink=router,
        output_paths={k: v for k, v in output_paths.items() if v},
        in_memory_csv_sinks=in_memory_csv_sinks,
    )


__all__ = [
    "AuditSheetSpec",
    "DedupBySpec",
    "DerivedDedupByGroupBySpec",
    "DerivedGroupBySpec",
    "DerivedOutputTargetSpec",
    "IDerivedAggregationSpec",
    "MetaSheetSpec",
    "OutputCompositionPlan",
    "OutputCompositionSpec",
    "OutputTargetSpec",
    "OutputTargetStats",
    "RouterRowSink",
    "ScalimOutputTargetWriteError",
    "TwoStageGroupBySpec",
    "build_output_composition",
    "required_demand_fields",
]
