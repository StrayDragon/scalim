"""`workflow` 共享输出资源: `workbook` 实现(内部模块).

说明:
- 承载 `workbook_sheet`/`workbook_append` 的计划构建、对齐与提交落盘
- 运行时需兼容 `Python 3.6`
"""

from abc import ABC
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, cast

from ....events.catalog import EVENT_DIAGNOSTIC_WARNING
from ....events.events import DiagnosticWarningEvent
from ....sinks.sink_base import create_temp_path
from ....vendor.compact.importlibx import require_optional_dependency
from ....vendor.compact.typing_extensionsx import override
from .workflow_resources_base import WorkflowResourceManagerBase, WorkflowWriteError, acquire_write_lock, release_write_lock
from .workflow_resources_csv import AppendSegment, build_alignment_mapping, describe_header_diff, iter_csv_rows, read_csv_header

# 内部实现仍沿用原有局部命名,减少重构噪音.
_AppendSegment = AppendSegment
_build_alignment_mapping = build_alignment_mapping
_describe_header_diff = describe_header_diff
_iter_csv_rows = iter_csv_rows
_read_csv_header = read_csv_header

if TYPE_CHECKING:
    from openpyxl import Workbook


def _get_openpyxl_workbook_class() -> "Type[Workbook]":
    openpyxl_mod = require_optional_dependency("openpyxl", context="scalim.dsl.by_yaml.runtime.workflow_resources")
    return cast("Any", openpyxl_mod).Workbook


def _best_effort_close_write_only_workbook_worksheets(workbook: Any) -> None:
    worksheets = getattr(workbook, "worksheets", None)
    if worksheets is None:
        return
    try:
        worksheets = list(worksheets)
    except TypeError:
        return
    for ws in worksheets:
        try:
            is_closed = bool(ws.closed)
        except AttributeError:
            continue
        if is_closed:
            continue
        with suppress(Exception):
            ws.close()


@dataclass
class _SheetPlan:
    sheet: str
    baseline_header: List[str]
    segments: List[_AppendSegment]


@dataclass
class _WorkbookPlan:
    resource_id: str
    path: str
    lock_path: Optional[Path]
    sheet_order: List[str]
    sheets: Dict[str, _SheetPlan]
    last_workflow_node_id: Optional[str] = None


class _WorkflowWorkbookResourceMixin(WorkflowResourceManagerBase, ABC):
    def _get_or_create_workbook(self, workbook_id: str, *, workflow_node_id: str) -> _WorkbookPlan:
        key = str(workbook_id)
        with self._lock:
            existing = cast("Optional[_WorkbookPlan]", self._workbooks.get(key))
            if existing is not None:
                return existing

        raw_path = self._workbook_defs.get(key)
        if raw_path is None:
            msg = "Unknown workbook resource id: {!r}".format(key)
            raise WorkflowWriteError(msg)
        lock_path = acquire_write_lock(raw_path)
        plan = _WorkbookPlan(
            resource_id=key,
            path=str(raw_path),
            lock_path=lock_path,
            sheet_order=[],
            sheets={},
        )
        with self._lock:
            self._workbooks[key] = plan
        self._emit_resource_create(workflow_node_id=str(workflow_node_id), resource_type="workbook", resource_id=key, path=str(raw_path))
        return plan

    def apply_workbook_sheet(
        self,
        *,
        workflow_node_id: str,
        workbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv_path: str,
        on_conflict: str,
    ) -> None:
        plan = self._get_or_create_workbook(workbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        action = "write"

        input_header = _read_csv_header(input_csv_path)

        pending_skip = False
        with self._lock:
            existing = plan.sheets.get(sheet_name)
            if existing is not None:
                if on_conflict == "skip":
                    action = "skip"
                    plan.last_workflow_node_id = str(workflow_node_id)
                    pending_skip = True
                if on_conflict == "error":
                    msg = "Sheet conflict (workbook_sheet): workbook={!r}, sheet={!r}".format(str(workbook_id), sheet_name)
                    raise WorkflowWriteError(msg, diff=["on_conflict=error", "existing_sheet=present"])
                if on_conflict == "overwrite":
                    action = "overwrite"

            if not pending_skip:
                if existing is None:
                    plan.sheet_order.append(sheet_name)

                mapping = _build_alignment_mapping(input_header, input_header)
                segment = _AppendSegment(
                    input_csv_path=str(input_csv_path),
                    header_policy="once",
                    mapping=mapping,
                    on_mismatch="error",
                    align_by="header",
                    input_header=input_header,
                )
                plan.sheets[sheet_name] = _SheetPlan(sheet=sheet_name, baseline_header=list(input_header), segments=[segment])
                plan.last_workflow_node_id = str(workflow_node_id)

        if pending_skip:
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
            return

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
        workbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv_path: str,
        align_by: str,
        header_policy: str,
        on_mismatch: str,
    ) -> None:
        plan = self._get_or_create_workbook(workbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        input_header = _read_csv_header(input_csv_path)

        pending_warning: Optional[DiagnosticWarningEvent] = None
        pending_warning_meta: Optional[Dict[str, object]] = None
        pending_skip = False

        with self._lock:
            sheet_plan = plan.sheets.get(sheet_name)
            if sheet_plan is None:
                plan.sheet_order.append(sheet_name)
                sheet_plan = _SheetPlan(sheet=sheet_name, baseline_header=list(input_header), segments=[])
                plan.sheets[sheet_name] = sheet_plan

            expected = list(sheet_plan.baseline_header)
            mapping = _build_alignment_mapping(expected, input_header)

            if list(input_header) != expected:
                diff = _describe_header_diff(expected, input_header)
                if on_mismatch == "error":
                    msg = "Field alignment mismatch (workbook_append): workbook={!r}, sheet={!r}".format(str(workbook_id), sheet_name)
                    raise WorkflowWriteError(msg, diff=diff)
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
                sheet_plan.segments.append(
                    _AppendSegment(
                        input_csv_path=str(input_csv_path),
                        header_policy=str(header_policy),
                        mapping=mapping,
                        on_mismatch=str(on_mismatch),
                        align_by=str(align_by),
                        input_header=list(input_header),
                    )
                )
                plan.last_workflow_node_id = str(workflow_node_id)

        if pending_warning is not None:
            _ = self._instrumentation.emit(EVENT_DIAGNOSTIC_WARNING, pending_warning, meta=pending_warning_meta)

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

    @override
    def _commit_workbook(self, plan: object) -> None:  # noqa: C901, PLR0912, PLR0915
        p = cast("_WorkbookPlan", plan)
        if not p.sheets:
            if p.lock_path is not None:
                release_write_lock(p.lock_path)
                p.lock_path = None
            return

        output_path = str(p.path)
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            workbook_cls = _get_openpyxl_workbook_class()
        except ImportError as exc:
            if p.lock_path is not None:
                release_write_lock(p.lock_path)
                p.lock_path = None
            raise WorkflowWriteError(str(exc)) from exc

        wb = workbook_cls(write_only=True)
        try:
            for sheet_name in p.sheet_order:
                sheet_plan = p.sheets.get(sheet_name)
                if sheet_plan is None:  # pragma: no cover
                    continue  # pragma: no cover
                ws = wb.create_sheet(str(sheet_name))
                header_written = False
                for seg in sheet_plan.segments:
                    if seg.header_policy == "always" or (seg.header_policy == "once" and not header_written):
                        _ = ws.append(list(sheet_plan.baseline_header))
                        header_written = True
                    # `never`: 不输出 `header`

                    for row in _iter_csv_rows(seg.input_csv_path):
                        out_row: List[object] = []
                        for idx in seg.mapping:
                            out_row.append(row[idx] if idx >= 0 and idx < len(row) else "")
                        _ = ws.append(out_row)

            temp_path = create_temp_path(output_path, ".xlsx.tmp")
            temp_obj = Path(temp_path)
            try:
                wb.save(temp_obj)
                _ = temp_obj.replace(output_path)
            except Exception as exc:
                with suppress(Exception):
                    if temp_obj.exists():
                        temp_obj.unlink()
                msg = "Workbook commit failed: {}: {}".format(type(exc).__name__, exc)
                raise WorkflowWriteError(msg) from exc
        except Exception:
            _best_effort_close_write_only_workbook_worksheets(wb)
            raise
        finally:
            with suppress(Exception):
                wb.close()
            if p.lock_path is not None:
                release_write_lock(p.lock_path)
                p.lock_path = None

        node_id = p.last_workflow_node_id or "__wf__commit"
        self._emit_resource_commit(workflow_node_id=node_id, resource_type="workbook", resource_id=p.resource_id, path=str(p.path))

    @override
    def _discard_workbook(self, plan: object, *, workflow_node_id: str, reason: str) -> None:
        p = cast("_WorkbookPlan", plan)
        if p.lock_path is not None:
            release_write_lock(p.lock_path)
            p.lock_path = None
        node_id = p.last_workflow_node_id or str(workflow_node_id)
        self._emit_resource_discard(
            workflow_node_id=node_id,
            resource_type="workbook",
            resource_id=p.resource_id,
            path=str(p.path),
            reason=str(reason),
        )


__all__ = [
    "SheetPlan",
    "WorkbookPlan",
    "WorkflowWorkbookResourceMixin",
    "_SheetPlan",
    "_WorkbookPlan",
    "_WorkflowWorkbookResourceMixin",
    "_best_effort_close_write_only_workbook_worksheets",
    "_get_openpyxl_workbook_class",
    "best_effort_close_write_only_workbook_worksheets",
    "get_openpyxl_workbook_class",
]

SheetPlan = _SheetPlan
WorkbookPlan = _WorkbookPlan
WorkflowWorkbookResourceMixin = _WorkflowWorkbookResourceMixin
best_effort_close_write_only_workbook_worksheets = _best_effort_close_write_only_workbook_worksheets
get_openpyxl_workbook_class = _get_openpyxl_workbook_class
