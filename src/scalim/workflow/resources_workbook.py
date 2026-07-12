"""`workflow` 共享输出资源: `workbook` 实现(内部模块).

说明:
- 承载 `workbook_sheet`/`workbook_append` 的计划构建、对齐与提交落盘
- 运行时需兼容 `Python 3.6`
"""

from abc import ABC
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Iterator, List, Optional, Tuple, Type, cast

from .._internal.utils.excel import escape_excel_formula
from .._internal.utils.openpyxl_helpers import (
    best_effort_close_write_only_workbook_worksheets as _best_effort_close_write_only_workbook_worksheets,
)
from .._internal.utils.openpyxl_helpers import save_openpyxl_workbook_atomic as _save_openpyxl_workbook_atomic_impl
from ..events import EventType
from ..events._events import DiagnosticWarningEvent
from ..typedefs import FieldValue
from ..vendor.compact.importlibx import require_optional_dependency
from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import dataclass, field
from .resources_base import ScalimWorkflowWriteError, WorkflowResourceManagerBase
from .resources_csv import build_alignment_mapping, describe_header_diff
from .tabular_artifacts import WorkflowTabularInput, materialize_aligned_tabular_rows, read_tabular_header

_build_alignment_mapping = build_alignment_mapping
_describe_header_diff = describe_header_diff

if TYPE_CHECKING:
    from openpyxl import Workbook


def _get_openpyxl_workbook_class() -> "Type[Workbook]":
    openpyxl_mod = require_optional_dependency("openpyxl", context="scalim.workflow.resources")
    return cast("Any", openpyxl_mod).Workbook  # pragma: allow-cast openpyxl module runtime boundary


def _save_openpyxl_workbook_atomic(workbook: object, *, output_path: str) -> None:
    try:
        _save_openpyxl_workbook_atomic_impl(workbook, output_path=output_path)
    except Exception as exc:
        msg = "Workbook commit failed: {}: {}".format(type(exc).__name__, exc)
        raise ScalimWorkflowWriteError(msg) from exc


def _sorted_workbook_segments(segments: List["_WorkbookSegment"]) -> List["_WorkbookSegment"]:
    return sorted(segments, key=lambda seg: (int(seg.decl_order), str(seg.producer_node_id)))


def _workbook_find_cutoff_index(segments: List["_WorkbookSegment"], *, producer_node_id: str) -> Optional[int]:
    needle = str(producer_node_id)
    for idx, seg in enumerate(segments):
        if str(seg.producer_node_id) == needle:
            return int(idx)
    return None


def _workbook_collect_visible_segments(
    segments: List["_WorkbookSegment"],
    *,
    cutoff_idx: int,
    producer_node_id: str,
    visible_producer_node_ids: FrozenSet[str],
) -> List[Tuple[str, List[List[FieldValue]]]]:
    producer = str(producer_node_id)
    visible = frozenset(str(x) for x in visible_producer_node_ids)
    out: List[Tuple[str, List[List[FieldValue]]]] = []
    for seg in segments[: int(cutoff_idx) + 1]:
        seg_producer = str(seg.producer_node_id)
        if seg_producer != producer and seg_producer not in visible:
            continue
        out.append((seg_producer, list(seg.rows)))
    return out


def _iter_workbook_row_dicts(
    baseline_header: List[str],
    segments: List[Tuple[str, List[List[FieldValue]]]],
) -> Iterator[Dict[str, FieldValue]]:
    for _seg_producer, seg_rows in segments:
        for row_values in seg_rows:
            row: Dict[str, FieldValue] = {}
            for idx, key in enumerate(baseline_header):
                row[str(key)] = row_values[idx] if idx >= 0 and idx < len(row_values) else ""
            yield row


def _iter_workbook_sheet_rows(sheet_plan: "_SheetPlan", *, allow_formulas: bool) -> Iterator[List[object]]:
    """将 `sheet_plan` 的自有类型化 `segments` 物化为待写入行(不依赖 `openpyxl`)."""

    header_written = False
    segments = _sorted_workbook_segments(sheet_plan.segments)
    export_fields = list(sheet_plan.export_header if sheet_plan.export_header is not None else sheet_plan.baseline_header)
    for seg in segments:
        if seg.header_policy == "always" or (seg.header_policy == "once" and not header_written):
            header = [escape_excel_formula(x, allow_formulas=bool(allow_formulas)) for x in list(export_fields)]
            yield header
            header_written = True
        # `never`: 不输出 `header`

        for row in seg.rows:
            out_row = [escape_excel_formula(v, allow_formulas=bool(allow_formulas)) for v in row]
            yield out_row


def _write_workbook_plan_to_openpyxl_workbook(workbook: object, plan: "_WorkbookPlan") -> None:
    wb = cast("Any", workbook)  # pragma: allow-cast openpyxl workbook runtime boundary
    for sheet_name in plan.sheet_order:
        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: sheet_plan always exists
        ws = wb.create_sheet(str(sheet_name))
        for row in _iter_workbook_sheet_rows(sheet_plan, allow_formulas=bool(plan.allow_formulas)):
            _ = ws.append(row)


@dataclass
class _WorkbookSegment:
    producer_node_id: str
    decl_order: int
    rows: List[List[FieldValue]]
    header_policy: str


@dataclass
class _SheetPlan:
    sheet: str
    baseline_header: List[str]
    export_header: Optional[List[str]] = None
    segments: List[_WorkbookSegment] = field(default_factory=list)


@dataclass
class _WorkbookPlan:
    resource_id: str
    path: str
    allow_formulas: bool
    sheet_decl_order: Dict[str, int]
    sheet_order: List[str]
    sheets: Dict[str, _SheetPlan]
    last_workflow_node_id: Optional[str] = None


class _WorkflowWorkbookResourceMixin(WorkflowResourceManagerBase, ABC):
    def _get_or_create_workbook(self, workbook_id: str, *, workflow_node_id: str) -> _WorkbookPlan:
        key = str(workbook_id)

        def _create() -> object:
            raw_path = self._workbook_defs.get(key)
            if raw_path is None:
                msg = "Unknown workbook resource id: {!r}".format(key)
                raise ScalimWorkflowWriteError(msg)
            return _WorkbookPlan(
                resource_id=key,
                path=str(raw_path),
                allow_formulas=bool(self._workbook_allow_formulas.get(key, True)),
                sheet_decl_order={},
                sheet_order=[],
                sheets={},
            )

        def _on_create(plan: object) -> None:
            p = cast("_WorkbookPlan", plan)  # pragma: allow-cast joinable plan typed narrowing
            self._emit_resource_create(
                workflow_node_id=str(workflow_node_id),
                resource_type="workbook",
                resource_id=key,
                path=str(p.path),
            )

        plan = self._get_or_create_plan(
            resource_type="workbook",
            resource_id=key,
            plans=self._workbooks,
            create_fn=_create,
            on_create=_on_create,
        )
        return cast("_WorkbookPlan", plan)  # pragma: allow-cast joinable plan typed narrowing

    def apply_workbook_sheet(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        workbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowTabularInput,
        on_conflict: str,
        export_header: Optional[Tuple[str, ...]] = None,
    ) -> None:
        plan = self._get_or_create_workbook(workbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        action = "write"

        input_header = read_tabular_header(input_csv)

        existing = plan.sheets.get(sheet_name)
        if existing is not None:
            if on_conflict == "skip":
                plan.last_workflow_node_id = str(workflow_node_id)
                self._emit_resource_write(
                    workflow_node_id=str(workflow_node_id),
                    resource_type="workbook",
                    resource_id=str(workbook_id),
                    path=str(plan.path),
                    write_kind="workbook_sheet",
                    action="skip",
                    input_node_id=str(input_node_id),
                    input_output_id=str(input_output_id),
                    sheet=sheet_name,
                )
                return
            if on_conflict == "error":
                msg = "Sheet conflict (workbook_sheet): workbook={!r}, sheet={!r}".format(str(workbook_id), sheet_name)
                raise ScalimWorkflowWriteError(msg, diff=["on_conflict=error", "existing_sheet=present"])
            if on_conflict == "overwrite":
                action = "overwrite"

        existing_decl_order = plan.sheet_decl_order.get(sheet_name)
        resolved_decl_order = int(decl_order)
        if existing_decl_order is None or resolved_decl_order < int(existing_decl_order):
            plan.sheet_decl_order[sheet_name] = resolved_decl_order
        plan.sheet_order = sorted(plan.sheet_decl_order.keys(), key=lambda name: (plan.sheet_decl_order.get(name, 0), str(name)))

        mapping = _build_alignment_mapping(input_header, input_header)
        rows = materialize_aligned_tabular_rows(input_header, mapping, input_tabular=input_csv)
        segment = _WorkbookSegment(
            producer_node_id=str(input_node_id),
            decl_order=int(decl_order),
            rows=rows,
            header_policy="once",
        )
        plan.sheets[sheet_name] = _SheetPlan(
            sheet=sheet_name,
            baseline_header=list(input_header),
            export_header=list(export_header) if export_header is not None else None,
            segments=[segment],
        )
        plan.last_workflow_node_id = str(workflow_node_id)

        self._emit_resource_write(
            workflow_node_id=str(workflow_node_id),
            resource_type="workbook",
            resource_id=str(workbook_id),
            path=str(plan.path),
            write_kind="workbook_sheet",
            action=action,
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            sheet=sheet_name,
        )

    def apply_workbook_append(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        workbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowTabularInput,
        align_by: str,
        header_policy: str,
        on_mismatch: str,
        export_header: Optional[Tuple[str, ...]] = None,
    ) -> None:
        plan = self._get_or_create_workbook(workbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        input_header = read_tabular_header(input_csv)

        pending_warning: Optional[DiagnosticWarningEvent] = None
        pending_warning_meta: Optional[Dict[str, object]] = None
        pending_skip = False

        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:
            plan.sheet_decl_order[sheet_name] = int(decl_order)
            plan.sheet_order = sorted(plan.sheet_decl_order.keys(), key=lambda name: (plan.sheet_decl_order.get(name, 0), str(name)))
            sheet_plan = _SheetPlan(
                sheet=sheet_name,
                baseline_header=list(input_header),
                export_header=list(export_header) if export_header is not None else None,
                segments=[],
            )
            plan.sheets[sheet_name] = sheet_plan
        else:
            existing_decl_order = plan.sheet_decl_order.get(sheet_name)
            resolved_decl_order = int(decl_order)
            if existing_decl_order is None or resolved_decl_order < int(existing_decl_order):
                plan.sheet_decl_order[sheet_name] = resolved_decl_order
                plan.sheet_order = sorted(
                    plan.sheet_decl_order.keys(),
                    key=lambda name: (plan.sheet_decl_order.get(name, 0), str(name)),
                )

        expected = list(sheet_plan.baseline_header)
        mapping = _build_alignment_mapping(expected, input_header)

        if list(input_header) != expected:
            diff = _describe_header_diff(expected, input_header)
            if on_mismatch == "error":
                msg = "Field alignment mismatch (workbook_append): workbook={!r}, sheet={!r}".format(str(workbook_id), sheet_name)
                raise ScalimWorkflowWriteError(msg, diff=diff)
            if on_mismatch == "warn":
                pending_warning = DiagnosticWarningEvent(
                    message="Field alignment mismatch (warn): workbook={!r}, sheet={!r}".format(str(workbook_id), sheet_name),
                    source_id=None,
                    field_id=None,
                    lookup_key={"expected": expected, "actual": list(input_header)},
                    row_id=None,
                )
                pending_warning_meta = {"workflow_exec_id": self._workflow_exec_id, "workflow_node_id": str(workflow_node_id)}
            if on_mismatch == "skip":
                plan.last_workflow_node_id = str(workflow_node_id)
                pending_skip = True

        if not pending_skip:
            _ = str(align_by)
            rows = materialize_aligned_tabular_rows(expected, mapping, input_tabular=input_csv)
            sheet_plan.segments.append(
                _WorkbookSegment(
                    producer_node_id=str(input_node_id),
                    decl_order=int(decl_order),
                    rows=rows,
                    header_policy=str(header_policy),
                )
            )
            plan.last_workflow_node_id = str(workflow_node_id)

        if pending_warning is not None:
            _ = self._instrumentation.emit(EventType.DIAGNOSTIC_WARNING, pending_warning, meta=pending_warning_meta)

        if pending_skip:
            self._emit_resource_write(
                workflow_node_id=str(workflow_node_id),
                resource_type="workbook",
                resource_id=str(workbook_id),
                path=str(plan.path),
                write_kind="workbook_append",
                action="skip",
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                sheet=sheet_name,
            )
            return

        self._emit_resource_write(
            workflow_node_id=str(workflow_node_id),
            resource_type="workbook",
            resource_id=str(workbook_id),
            path=str(plan.path),
            write_kind="workbook_append",
            action="append",
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            sheet=sheet_name,
        )

    def iter_workbook_sheet_rows(
        self,
        *,
        consumer_node_id: str,
        visible_producer_node_ids: FrozenSet[str],
        producer_node_id: str,
        workbook_id: str,
        sheet: str,
    ) -> Iterator[Dict[str, FieldValue]]:
        """读取 `workbook` 的行快照(按 `ref.node` 截断;按依赖可见性过滤)."""

        _ = str(consumer_node_id)
        producer = str(producer_node_id)
        wb_id = str(workbook_id)
        sheet_name = str(sheet)
        visible = frozenset(str(x) for x in visible_producer_node_ids)

        plan = cast("Optional[_WorkbookPlan]", self._workbooks.get(wb_id))  # pragma: allow-cast workbook plan typed narrowing
        if plan is None:
            msg = "Unknown workbook resource id: {!r}".format(wb_id)
            raise ValueError(msg)
        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:
            msg = "Unknown workbook sheet: workbook={!r}, sheet={!r}".format(wb_id, sheet_name)
            raise ValueError(msg)

        ordered_segments = _sorted_workbook_segments(list(sheet_plan.segments))
        cutoff_idx = _workbook_find_cutoff_index(ordered_segments, producer_node_id=producer)
        if cutoff_idx is None:
            msg = "Unknown workbook ref node for sheet: node={!r}, workbook={!r}, sheet={!r}".format(producer, wb_id, sheet_name)
            raise ValueError(msg)

        baseline_header = list(sheet_plan.baseline_header)
        segments = _workbook_collect_visible_segments(
            ordered_segments,
            cutoff_idx=int(cutoff_idx),
            producer_node_id=producer,
            visible_producer_node_ids=visible,
        )
        return _iter_workbook_row_dicts(baseline_header, segments)

    @override
    def _commit_workbook(self, plan: object) -> None:
        p = cast("_WorkbookPlan", plan)  # pragma: allow-cast joinable plan typed narrowing
        if not p.sheets:
            node_id = p.last_workflow_node_id or "__wf__commit"
            self._release_workbook_plan_segments(p, workflow_node_id=str(node_id), release_reason="commit")
            return

        final_path = str(p.path)
        staging_path = self._staging_path_for_final_output(final_path)

        try:
            workbook_cls = _get_openpyxl_workbook_class()
        except ImportError as exc:
            raise ScalimWorkflowWriteError(str(exc)) from exc

        wb = workbook_cls(write_only=True)
        try:
            _write_workbook_plan_to_openpyxl_workbook(wb, p)
            _save_openpyxl_workbook_atomic(wb, output_path=staging_path)
        except Exception:
            _best_effort_close_write_only_workbook_worksheets(wb)
            raise
        finally:
            with suppress(Exception):
                wb.close()

        node_id = p.last_workflow_node_id or "__wf__commit"
        self._register_staged_output(
            resource_type="workbook",
            resource_id=p.resource_id,
            workflow_node_id=str(node_id),
            staged_path=str(staging_path),
            final_path=str(final_path),
        )
        self._release_workbook_plan_segments(p, workflow_node_id=str(node_id), release_reason="commit")

    @override
    def _discard_workbook(self, plan: object, *, workflow_node_id: str, reason: str) -> None:
        p = cast("_WorkbookPlan", plan)  # pragma: allow-cast joinable plan typed narrowing
        node_id = p.last_workflow_node_id or str(workflow_node_id)
        self._emit_resource_discard(
            workflow_node_id=node_id,
            resource_type="workbook",
            resource_id=p.resource_id,
            path=str(p.path),
            reason=str(reason),
        )
        self._release_workbook_plan_segments(p, workflow_node_id=str(node_id), release_reason="discard")

    def _release_workbook_plan_segments(self, plan: "_WorkbookPlan", *, workflow_node_id: str, release_reason: str) -> None:
        for sheet_plan in plan.sheets.values():
            for seg in sheet_plan.segments:
                seg.rows = []
            sheet_plan.segments = []
        self._log_plan_segment_release(
            workflow_node_id=str(workflow_node_id),
            resource_type="workbook",
            resource_id=plan.resource_id,
            path=str(plan.path),
            release_reason=str(release_reason),
        )
        _ = self._workbooks.pop(str(plan.resource_id), None)


__all__ = (
    "SheetPlan",
    "WorkbookPlan",
    "WorkflowWorkbookResourceMixin",
    "best_effort_close_write_only_workbook_worksheets",
    "get_openpyxl_workbook_class",
)

SheetPlan = _SheetPlan
WorkbookPlan = _WorkbookPlan
WorkflowWorkbookResourceMixin = _WorkflowWorkbookResourceMixin
best_effort_close_write_only_workbook_worksheets = _best_effort_close_write_only_workbook_worksheets
get_openpyxl_workbook_class = _get_openpyxl_workbook_class
