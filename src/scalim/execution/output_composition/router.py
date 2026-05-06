from __future__ import absolute_import

import hashlib
import time
from typing import List, Optional, Sequence, Tuple

from ..._project_constants import VERSION as SCALIM_VERSION
from ...events import EventType
from ...events._events import OutputTargetEndEvent
from ...exceptions import ScalimExecutionError
from ...ob.hub import InstrumentationHub
from ...sinks import BaseRowSink, ExcelWorkbookSink, IRowSink
from ...typedefs import FailurePolicy, RowData
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from ..derived_outputs import AggregatingRowSink, fingerprint_for_meta
from .policy import parse_output_failure_policy
from .sinks import RowCounter
from .specs import OutputRowPredicate, OutputTargetStats


class ScalimOutputTargetWriteError(ScalimExecutionError):
    target_id: str

    def __init__(self, target_id: str, exc: Exception) -> None:
        super(ScalimOutputTargetWriteError, self).__init__("Output target failed: {}: {}".format(target_id, exc))
        self.target_id = str(target_id)


def sha256_text(value: str) -> str:
    digest = hashlib.sha256()
    digest.update(value.encode("utf-8", errors="replace"))
    return digest.hexdigest()


def as_single_line(value: str) -> str:
    # 避免 `meta/audit` 出现多行单元格,并保持输出可预测.
    return " ".join(str(value).splitlines())


def truncate_text(value: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "…(truncated)"


@dataclass
class RouteState:
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
    output_counter: Optional[RowCounter] = None


@dataclass
class FinalTargetState:
    target_id: str
    sink: IRowSink
    output_counter: RowCounter
    output_path: Optional[str]
    sheet_name: Optional[str]


class RouterRowSink(BaseRowSink):
    """同一行数据流的多路输出路由器(流式).

    负责:
    - 分发与过滤
    - 失败策略
    - 按输出目标统计(行数/耗时/错误)
    - `close()` 时写入元信息/审计并保存工作簿容器
    """

    _routes: List[RouteState]
    _failure_policy: str
    _workbook_resources: List["ExcelWorkbookSink"]
    _meta_target: Optional[FinalTargetState]
    _audit_target: Optional[FinalTargetState]
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
        routes: Sequence[RouteState],
        failure_policy: str,
        workbook_resources: Sequence["ExcelWorkbookSink"],
        meta_target: Optional[FinalTargetState] = None,
        audit_target: Optional[FinalTargetState] = None,
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
        self._failure_policy = parse_output_failure_policy(failure_policy)
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
                error_message_hash = sha256_text(raw)
                if self._include_full_error_message:
                    normalized = as_single_line(raw)
                    error_message = truncate_text(normalized, max_chars=2000)
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
                if self._failure_policy == FailurePolicy.PRIMARY_ONLY and not route.is_primary:
                    route.disabled = True
                    continue
                raise ScalimOutputTargetWriteError(route.target_id, exc) from exc
            finally:
                route.duration_seconds += time.perf_counter() - start

    def _close_route_sink(self, route: RouteState) -> None:
        try:
            route.sink.close()
        except Exception as exc:
            route.error_count += 1
            if route.first_error is None:
                route.first_error = exc
            if self._failure_policy == FailurePolicy.PRIMARY_ONLY and not route.is_primary:
                route.disabled = True
                return
            raise ScalimOutputTargetWriteError(route.target_id, exc) from exc

    def _routes_by_output_path(self, output_path: Optional[str]) -> List[RouteState]:
        key = str(output_path or "")
        return [r for r in self._routes if str(r.output_path or "") == key]

    def _record_routes_error(self, routes: Sequence[RouteState], exc: Exception) -> None:
        for r in routes:
            r.error_count += 1
            if r.first_error is None:
                r.first_error = exc

    def _disable_routes(self, routes: Sequence[RouteState]) -> None:
        for r in routes:
            r.disabled = True

    def _has_primary_route(self, routes: Sequence[RouteState]) -> bool:
        return any(r.is_primary for r in routes)

    def _select_target_id(self, routes: Sequence[RouteState]) -> str:
        # 优先选择主输出的 `target_id`,便于定位问题.
        for r in routes:
            if r.is_primary:
                return str(r.target_id)
        return str(routes[0].target_id)

    def _close_workbook_resource(self, wb: "ExcelWorkbookSink") -> None:
        try:
            wb.close()
        except Exception as exc:
            related = self._routes_by_output_path(wb.output_path)
            if not related:
                raise

            self._record_routes_error(related, exc)

            if self._failure_policy == FailurePolicy.PRIMARY_ONLY and not self._has_primary_route(related):
                self._disable_routes(related)
                return

            target_id = self._select_target_id(related)
            raise ScalimOutputTargetWriteError(target_id, exc) from exc

    def _emit_target_end_events(self) -> None:
        if not self._emit_events or self._instrumentation is None:
            return
        for stat in self.get_target_stats():
            _ = self._instrumentation.emit(
                EventType.OUTPUT_TARGET_END,
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
            self._close_workbook_resource(wb)

        # 4) 输出级观测结束事件
        self._emit_target_end_events()

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
                msg_hash = sha256_text(raw)
                if self._include_full_error_message:
                    normalized = as_single_line(raw)
                    msg_out = truncate_text(normalized, max_chars=2000)
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
