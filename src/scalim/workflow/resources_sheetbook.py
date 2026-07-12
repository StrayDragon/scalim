"""`workflow` 共享输出资源: `sheetbook` 实现(内部模块).

说明:
- 承载 `sheetbook_sheet`/`sheetbook_append` 的内存物化、读取与导出
- 运行时需兼容 `Python 3.6`
"""

from abc import ABC
from contextlib import suppress
from typing import Any, Dict, FrozenSet, Iterator, List, Optional, Tuple, cast

from .._internal.utils.excel import escape_excel_formula
from .._internal.utils.openpyxl_helpers import save_openpyxl_workbook_atomic as _save_openpyxl_workbook_atomic_impl
from ..events import EventType
from ..events._events import DiagnosticWarningEvent
from ..typedefs import FieldValue
from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import dataclass
from .resources_base import ScalimWorkflowWriteError, WorkflowResourceManagerBase
from .resources_csv import build_alignment_mapping, describe_header_diff
from .resources_workbook import best_effort_close_write_only_workbook_worksheets, get_openpyxl_workbook_class
from .tabular_artifacts import WorkflowTabularInput, materialize_aligned_tabular_rows, read_tabular_header

# 内部实现仍沿用原有局部命名,减少重构噪音.
_build_alignment_mapping = build_alignment_mapping
_describe_header_diff = describe_header_diff
_best_effort_close_write_only_workbook_worksheets = best_effort_close_write_only_workbook_worksheets
_get_openpyxl_workbook_class = get_openpyxl_workbook_class


def _save_openpyxl_workbook_atomic(workbook: object, *, output_path: str) -> None:
    try:
        _save_openpyxl_workbook_atomic_impl(workbook, output_path=output_path)
    except Exception as exc:
        msg = "Sheetbook export failed: {}: {}".format(type(exc).__name__, exc)
        raise ScalimWorkflowWriteError(msg) from exc


def _sheetbook_has_alignment_mismatch(expected: List[str], input_header: List[str], *, align_by: str) -> bool:
    if str(align_by) == "field_id":
        exp_set = {str(x) for x in expected}
        act_set = {str(x) for x in input_header}
        missing = exp_set.difference(act_set)
        extra = act_set.difference(exp_set)
        return bool(missing or extra)
    return list(input_header) != list(expected)


def _sheetbook_decide_alignment_action(expected: List[str], input_header: List[str], *, align_by: str, on_mismatch: str) -> str:
    if not _sheetbook_has_alignment_mismatch(expected, input_header, align_by=str(align_by)):
        return "ok"
    if str(on_mismatch) in {"error", "warn", "skip"}:
        return str(on_mismatch)
    return "error"


def _sheetbook_has_duplicate_producer_write(segments: List["_SheetBookSegment"], *, producer_node_id: str) -> bool:
    needle = str(producer_node_id)
    return any(str(seg.producer_node_id) == needle for seg in segments)


def _sheetbook_find_cutoff_index(segments: List["_SheetBookSegment"], *, producer_node_id: str) -> Optional[int]:
    needle = str(producer_node_id)
    for idx, seg in enumerate(segments):
        if str(seg.producer_node_id) == needle:
            return int(idx)
    return None


def _sheetbook_collect_visible_segments(
    segments: List["_SheetBookSegment"],
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


def _iter_sheetbook_row_dicts(
    baseline_header: List[str],
    segments: List[Tuple[str, List[List[FieldValue]]]],
) -> Iterator[Dict[str, FieldValue]]:
    for _seg_producer, seg_rows in segments:
        for row_values in seg_rows:
            row: Dict[str, FieldValue] = {}
            for idx, key in enumerate(baseline_header):
                row[str(key)] = row_values[idx] if idx >= 0 and idx < len(row_values) else ""
            yield row


def _sorted_sheetbook_segments(segments: List["_SheetBookSegment"]) -> List["_SheetBookSegment"]:
    return sorted(segments, key=lambda seg: (int(seg.decl_order), str(seg.producer_node_id)))


def _write_sheetbook_plan_to_openpyxl_workbook(workbook: object, plan: "_SheetBookPlan") -> None:
    wb = cast("Any", workbook)  # pragma: allow-cast openpyxl workbook runtime boundary
    for sheet_name in plan.sheet_order:
        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: sheet_plan always exists
        ws = wb.create_sheet(str(sheet_name))
        header_written = False
        fields = list(sheet_plan.export_header if sheet_plan.export_header is not None else sheet_plan.baseline_header)
        escaped_fields = [escape_excel_formula(x, allow_formulas=bool(plan.export_allow_formulas)) for x in fields]
        for seg in _sorted_sheetbook_segments(sheet_plan.segments):
            if seg.header_policy == "always" or (seg.header_policy == "once" and not header_written):
                _ = ws.append(list(escaped_fields))
                header_written = True
            # `never`: 不输出表头

            for row in seg.rows:
                out_row = [escape_excel_formula(v, allow_formulas=bool(plan.export_allow_formulas)) for v in row]
                _ = ws.append(out_row)


@dataclass(frozen=True)
class SheetBookDef:
    resource_id: str
    budget_max_sheets: int
    budget_max_total_cells: int
    export_path: Optional[str]
    export_allow_formulas: bool = True


@dataclass
class _SheetBookSegment:
    producer_node_id: str
    decl_order: int
    rows: List[List[FieldValue]]
    header_policy: str


@dataclass
class _SheetBookSheetPlan:
    sheet: str
    baseline_header: List[str]
    export_header: Optional[List[str]]
    segments: List[_SheetBookSegment]
    cell_count: int = 0


@dataclass
class _SheetBookPlan:
    resource_id: str
    budget_max_sheets: int
    budget_max_total_cells: int
    export_path: Optional[str]
    export_allow_formulas: bool
    sheet_decl_order: Dict[str, int]
    sheet_order: List[str]
    sheets: Dict[str, _SheetBookSheetPlan]
    total_cells: int = 0
    last_workflow_node_id: Optional[str] = None


class _WorkflowSheetBookResourceMixin(WorkflowResourceManagerBase, ABC):
    @staticmethod
    def _sheetbook_has_alignment_mismatch(expected: List[str], input_header: List[str], *, align_by: str) -> bool:
        return _sheetbook_has_alignment_mismatch(expected, input_header, align_by=str(align_by))

    @staticmethod
    def _normalize_sheetbook_export_header(expected: List[str], export_header: Optional[Tuple[str, ...]]) -> List[str]:
        if export_header is None:
            return list(expected)

        resolved = [str(x) for x in export_header]
        if len(resolved) != len(expected):
            msg = "Sheetbook export header width mismatch: expected={}, actual={}".format(len(expected), len(resolved))
            raise ScalimWorkflowWriteError(msg)
        return resolved

    @classmethod
    def _resolve_sheetbook_export_header(
        cls,
        expected: List[str],
        *,
        export_header: Optional[Tuple[str, ...]],
        existing_export_header: Optional[List[str]] = None,
        sheetbook_id: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> List[str]:
        resolved = cls._normalize_sheetbook_export_header(expected, export_header)
        if existing_export_header is not None and list(existing_export_header) != list(resolved):
            msg = "Sheetbook export header baseline mismatch: sheetbook={!r}, sheet={!r}".format(
                str(sheetbook_id),
                str(sheet_name),
            )
            diff = [
                "existing_export_header={!r}".format(list(existing_export_header)),
                "new_export_header={!r}".format(list(resolved)),
            ]
            raise ScalimWorkflowWriteError(msg, diff=diff)
        return resolved

    def _emit_sheetbook_commit(self, plan: _SheetBookPlan, *, display_path: str) -> None:
        node_id = plan.last_workflow_node_id or "__wf__commit"
        self._emit_resource_commit(
            workflow_node_id=node_id, resource_type="sheetbook", resource_id=plan.resource_id, path=str(display_path)
        )

    def _sheetbook_sheet_prepare_action(
        self,
        plan: _SheetBookPlan,
        *,
        workflow_node_id: str,
        sheetbook_id: str,
        sheet_name: str,
        on_conflict: str,
    ) -> Tuple[str, bool]:
        action = "write"
        pending_skip = False
        existing = plan.sheets.get(sheet_name)
        if existing is not None:
            if on_conflict == "skip":
                action = "skip"
                plan.last_workflow_node_id = str(workflow_node_id)
                pending_skip = True
            if on_conflict == "error":
                msg = "Sheet conflict (sheetbook_sheet): sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name)
                raise ScalimWorkflowWriteError(msg, diff=["on_conflict=error", "existing_sheet=present"])
            if on_conflict == "overwrite":
                action = "overwrite"
        else:
            max_sheets_limit = int(plan.budget_max_sheets)
            if max_sheets_limit > 0 and len(plan.sheets) >= max_sheets_limit:
                msg = "Sheetbook budget exceeded: max_sheets (sheetbook={!r})".format(str(sheetbook_id))
                diff = [
                    "budget.max_sheets={}".format(int(plan.budget_max_sheets)),
                    "current_sheets={}".format(len(plan.sheets)),
                    "new_sheet={!r}".format(sheet_name),
                ]
                raise ScalimWorkflowWriteError(msg, diff=diff)
        return action, pending_skip

    def _sheetbook_sheet_store(
        self,
        plan: _SheetBookPlan,
        *,
        workflow_node_id: str,
        sheet_name: str,
        decl_order: int,
        input_node_id: str,
        expected: List[str],
        export_header: Optional[Tuple[str, ...]],
        rows: List[List[FieldValue]],
        new_sheet_cells: int,
    ) -> None:
        existing = plan.sheets.get(sheet_name)
        old_cells = 0
        if existing is not None:
            old_cells = int(existing.cell_count)

        new_total = int(plan.total_cells) - int(old_cells) + int(new_sheet_cells)
        self._check_sheetbook_budget(plan, new_total_cells=new_total)

        existing_decl_order = plan.sheet_decl_order.get(sheet_name)
        resolved_decl_order = int(decl_order)
        if existing_decl_order is None or resolved_decl_order < int(existing_decl_order):
            plan.sheet_decl_order[sheet_name] = resolved_decl_order
        plan.sheet_order = sorted(plan.sheet_decl_order.keys(), key=lambda name: (plan.sheet_decl_order.get(name, 0), str(name)))

        sheet_plan = _SheetBookSheetPlan(
            sheet=sheet_name,
            baseline_header=list(expected),
            export_header=self._resolve_sheetbook_export_header(
                list(expected),
                export_header=export_header,
                sheetbook_id=plan.resource_id,
                sheet_name=sheet_name,
            ),
            segments=[],
            cell_count=int(new_sheet_cells),
        )
        sheet_plan.segments.append(
            _SheetBookSegment(
                producer_node_id=str(input_node_id),
                decl_order=int(decl_order),
                rows=rows,
                header_policy="once",
            )
        )
        plan.sheets[sheet_name] = sheet_plan
        plan.total_cells = int(new_total)
        plan.last_workflow_node_id = str(workflow_node_id)

    def _sheetbook_append_prepare(
        self,
        plan: _SheetBookPlan,
        *,
        workflow_node_id: str,
        sheetbook_id: str,
        sheet_name: str,
        decl_order: int,
        input_node_id: str,
        input_header: List[str],
        export_header: Optional[Tuple[str, ...]],
        align_by: str,
        on_mismatch: str,
    ) -> Tuple[List[str], List[int], Optional[DiagnosticWarningEvent], Optional[Dict[str, object]], bool]:
        msg: str
        pending_warning: Optional[DiagnosticWarningEvent] = None
        pending_warning_meta: Optional[Dict[str, object]] = None
        pending_skip = False

        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:
            max_sheets_limit = int(plan.budget_max_sheets)
            if max_sheets_limit > 0 and len(plan.sheets) >= max_sheets_limit:
                msg = "Sheetbook budget exceeded: max_sheets (sheetbook={!r})".format(str(sheetbook_id))
                diff = [
                    "budget.max_sheets={}".format(int(plan.budget_max_sheets)),
                    "current_sheets={}".format(len(plan.sheets)),
                    "new_sheet={!r}".format(sheet_name),
                ]
                raise ScalimWorkflowWriteError(msg, diff=diff)
            plan.sheet_decl_order[sheet_name] = int(decl_order)
            plan.sheet_order = sorted(plan.sheet_decl_order.keys(), key=lambda name: (plan.sheet_decl_order.get(name, 0), str(name)))
            sheet_plan = _SheetBookSheetPlan(
                sheet=sheet_name,
                baseline_header=list(input_header),
                export_header=self._resolve_sheetbook_export_header(
                    list(input_header),
                    export_header=export_header,
                    sheetbook_id=plan.resource_id,
                    sheet_name=sheet_name,
                ),
                segments=[],
                cell_count=0,
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
            _ = self._resolve_sheetbook_export_header(
                list(sheet_plan.baseline_header),
                export_header=export_header,
                existing_export_header=sheet_plan.export_header,
                sheetbook_id=plan.resource_id,
                sheet_name=sheet_name,
            )

        expected = list(sheet_plan.baseline_header)
        mapping = _build_alignment_mapping(expected, input_header)

        action = _sheetbook_decide_alignment_action(expected, input_header, align_by=str(align_by), on_mismatch=str(on_mismatch))
        if action != "ok":
            diff = _describe_header_diff(expected, input_header)
            if action == "error":
                msg = "Field alignment mismatch (sheetbook_append): sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name)
                raise ScalimWorkflowWriteError(msg, diff=diff)
            if action == "warn":
                pending_warning = DiagnosticWarningEvent(
                    message="Field alignment mismatch (warn): sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name),
                    source_id=None,
                    field_id=None,
                    lookup_key={"expected": expected, "actual": list(input_header)},
                    row_id=None,
                )
                pending_warning_meta = {"workflow_exec_id": self._workflow_exec_id, "workflow_node_id": str(workflow_node_id)}
            if action == "skip":
                plan.last_workflow_node_id = str(workflow_node_id)
                pending_skip = True

        # 重复写入检测: 同一生产者不应写入同一工作表多次.
        if not pending_skip and _sheetbook_has_duplicate_producer_write(sheet_plan.segments, producer_node_id=str(input_node_id)):
            msg = "Duplicate sheetbook write for the same producer: sheetbook={!r}, sheet={!r}, producer={!r}".format(
                str(sheetbook_id),
                sheet_name,
                str(input_node_id),
            )
            raise ScalimWorkflowWriteError(msg, diff=["producer_node_id={!r}".format(str(input_node_id))])
        return expected, mapping, pending_warning, pending_warning_meta, pending_skip

    def _sheetbook_append_apply(
        self,
        plan: _SheetBookPlan,
        *,
        sheetbook_id: str,
        sheet_name: str,
        append_cells: int,
        workflow_node_id: str,
        input_node_id: str,
        decl_order: int,
        rows: List[List[FieldValue]],
        header_policy: str,
    ) -> None:
        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:  # pragma: no cover  # pragma: allow-no-cover unreachable: sheet_plan always exists
            msg = "Sheetbook sheet missing during append: sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name)
            raise ScalimWorkflowWriteError(msg)

        new_total = int(plan.total_cells) + int(append_cells)
        self._check_sheetbook_budget(plan, new_total_cells=new_total)
        sheet_plan.segments.append(
            _SheetBookSegment(
                producer_node_id=str(input_node_id),
                decl_order=int(decl_order),
                rows=rows,
                header_policy=str(header_policy),
            )
        )
        sheet_plan.cell_count = int(sheet_plan.cell_count) + int(append_cells)
        plan.total_cells = int(new_total)
        plan.last_workflow_node_id = str(workflow_node_id)

    def _get_or_create_sheetbook(self, sheetbook_id: str, *, workflow_node_id: str) -> _SheetBookPlan:
        key = str(sheetbook_id)
        existing = cast("Optional[_SheetBookPlan]", self._sheetbooks.get(key))  # pragma: allow-cast sheetbook plan typed narrowing
        if existing is not None:
            return existing

        raw_def = self._sheetbook_defs.get(key)
        if raw_def is None:
            msg = "Unknown sheetbook resource id: {!r}".format(key)
            raise ScalimWorkflowWriteError(msg)

        raw_def = cast("SheetBookDef", raw_def)  # pragma: allow-cast sheetbook def typed narrowing
        plan = SheetBookPlan(
            resource_id=str(raw_def.resource_id),
            budget_max_sheets=int(raw_def.budget_max_sheets),
            budget_max_total_cells=int(raw_def.budget_max_total_cells),
            export_path=str(raw_def.export_path) if raw_def.export_path is not None else None,
            export_allow_formulas=bool(raw_def.export_allow_formulas),
            sheet_decl_order={},
            sheet_order=[],
            sheets={},
        )
        self._sheetbooks[key] = plan

        display_path = plan.export_path if plan.export_path is not None else "<memory>"
        self._emit_resource_create(
            workflow_node_id=str(workflow_node_id),
            resource_type="sheetbook",
            resource_id=str(key),
            path=str(display_path),
        )
        return plan

    def _check_sheetbook_budget(
        self,
        plan: _SheetBookPlan,
        *,
        new_total_cells: int,
        allow_over_budget: bool = False,
    ) -> None:
        if allow_over_budget:  # pragma: no cover  # pragma: allow-no-cover test-only budget bypass
            return  # pragma: no cover  # pragma: allow-no-cover test-only budget bypass
        limit = int(plan.budget_max_total_cells)
        if limit <= 0:
            return
        if int(new_total_cells) <= limit:
            return
        diff = [
            "budget.max_total_cells={}".format(limit),
            "new_total_cells={}".format(int(new_total_cells)),
        ]
        msg = "Sheetbook budget exceeded: sheetbook={!r}".format(str(plan.resource_id))
        raise ScalimWorkflowWriteError(msg, diff=diff)

    def apply_sheetbook_sheet(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        sheetbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowTabularInput,
        on_conflict: str,
        export_header: Optional[Tuple[str, ...]] = None,
    ) -> None:
        plan = self._get_or_create_sheetbook(sheetbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        input_header = read_tabular_header(input_csv)
        action, pending_skip = self._sheetbook_sheet_prepare_action(
            plan,
            workflow_node_id=str(workflow_node_id),
            sheetbook_id=str(sheetbook_id),
            sheet_name=sheet_name,
            on_conflict=str(on_conflict),
        )

        if pending_skip:
            display_path = plan.export_path if plan.export_path is not None else "<memory>"
            self._emit_resource_write(
                workflow_node_id=str(workflow_node_id),
                resource_type="sheetbook",
                resource_id=str(sheetbook_id),
                path=str(display_path),
                write_kind="sheetbook_sheet",
                action=action,
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                sheet=sheet_name,
            )
            return

        expected = list(input_header)
        mapping = _build_alignment_mapping(expected, input_header)

        rows = materialize_aligned_tabular_rows(expected, mapping, input_tabular=input_csv)
        row_count = len(rows)
        new_sheet_cells = int(row_count) * len(expected)

        self._sheetbook_sheet_store(
            plan,
            workflow_node_id=str(workflow_node_id),
            sheet_name=sheet_name,
            decl_order=int(decl_order),
            input_node_id=str(input_node_id),
            expected=expected,
            export_header=export_header,
            rows=rows,
            new_sheet_cells=int(new_sheet_cells),
        )

        display_path = plan.export_path if plan.export_path is not None else "<memory>"
        self._emit_resource_write(
            workflow_node_id=str(workflow_node_id),
            resource_type="sheetbook",
            resource_id=str(sheetbook_id),
            path=str(display_path),
            write_kind="sheetbook_sheet",
            action=action,
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            sheet=sheet_name,
        )

    def apply_sheetbook_append(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        sheetbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowTabularInput,
        align_by: str,
        header_policy: str,
        on_mismatch: str,
        export_header: Optional[Tuple[str, ...]] = None,
    ) -> None:
        if str(align_by or "field_id") == "header":
            msg = (
                "xlsx_memory/sheetbook does not support align_by=header; "
                "internal rows only use canonical field keys. Migrate to align_by=field_id "
                "and keep header_fields_output_by for export display"
            )
            raise ScalimWorkflowWriteError(msg, diff=["align_by='header'"])

        plan = self._get_or_create_sheetbook(sheetbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        input_header = read_tabular_header(input_csv)
        expected, mapping, pending_warning, pending_warning_meta, pending_skip = self._sheetbook_append_prepare(
            plan,
            workflow_node_id=str(workflow_node_id),
            sheetbook_id=str(sheetbook_id),
            sheet_name=sheet_name,
            decl_order=int(decl_order),
            input_node_id=str(input_node_id),
            input_header=list(input_header),
            export_header=export_header,
            align_by=str(align_by),
            on_mismatch=str(on_mismatch),
        )

        if pending_warning is not None:
            _ = self._instrumentation.emit(EventType.DIAGNOSTIC_WARNING, pending_warning, meta=pending_warning_meta)

        if pending_skip:
            display_path = plan.export_path if plan.export_path is not None else "<memory>"
            self._emit_resource_write(
                workflow_node_id=str(workflow_node_id),
                resource_type="sheetbook",
                resource_id=str(sheetbook_id),
                path=str(display_path),
                write_kind="sheetbook_append",
                action="skip",
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                sheet=sheet_name,
            )
            return

        rows = materialize_aligned_tabular_rows(expected, mapping, input_tabular=input_csv)

        append_rows = len(rows)
        append_cells = int(append_rows) * len(expected)

        self._sheetbook_append_apply(
            plan,
            sheetbook_id=str(sheetbook_id),
            sheet_name=sheet_name,
            append_cells=int(append_cells),
            workflow_node_id=str(workflow_node_id),
            input_node_id=str(input_node_id),
            decl_order=int(decl_order),
            rows=rows,
            header_policy=str(header_policy),
        )

        display_path = plan.export_path if plan.export_path is not None else "<memory>"
        self._emit_resource_write(
            workflow_node_id=str(workflow_node_id),
            resource_type="sheetbook",
            resource_id=str(sheetbook_id),
            path=str(display_path),
            write_kind="sheetbook_append",
            action="append",
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            sheet=sheet_name,
        )

    def iter_sheetbook_sheet_rows(
        self,
        *,
        consumer_node_id: str,
        visible_producer_node_ids: FrozenSet[str],
        producer_node_id: str,
        sheetbook_id: str,
        sheet: str,
    ) -> Iterator[Dict[str, FieldValue]]:
        """读取 `sheetbook` 的行快照(按 `ref.node` 截断;按依赖可见性过滤).

        返回: `Iterator[Dict[str, FieldValue]]`.
        """
        _ = str(consumer_node_id)
        producer = str(producer_node_id)
        sb_id = str(sheetbook_id)
        sheet_name = str(sheet)
        visible = frozenset(str(x) for x in visible_producer_node_ids)

        plan = cast("Optional[_SheetBookPlan]", self._sheetbooks.get(sb_id))  # pragma: allow-cast sheetbook plan typed narrowing
        if plan is None:
            msg = "Unknown sheetbook resource id: {!r}".format(sb_id)
            raise ValueError(msg)
        sheet_plan = plan.sheets.get(sheet_name)
        if sheet_plan is None:
            msg = "Unknown sheetbook sheet: sheetbook={!r}, sheet={!r}".format(sb_id, sheet_name)
            raise ValueError(msg)

        ordered_segments = _sorted_sheetbook_segments(list(sheet_plan.segments))
        cutoff_idx = _sheetbook_find_cutoff_index(ordered_segments, producer_node_id=producer)
        if cutoff_idx is None:
            msg = "Unknown sheetbook ref node for sheet: node={!r}, sheetbook={!r}, sheet={!r}".format(producer, sb_id, sheet_name)
            raise ValueError(msg)

        baseline_header = list(sheet_plan.baseline_header)
        segments = _sheetbook_collect_visible_segments(
            ordered_segments,
            cutoff_idx=int(cutoff_idx),
            producer_node_id=producer,
            visible_producer_node_ids=visible,
        )

        return _iter_sheetbook_row_dicts(baseline_header, segments)

    @override
    def _commit_sheetbook(self, plan: object) -> None:
        p = cast("_SheetBookPlan", plan)  # pragma: allow-cast sheetbook plan typed narrowing
        export_path = p.export_path
        display_path = export_path if export_path is not None else "<memory>"
        node_id = p.last_workflow_node_id or "__wf__commit"
        if export_path is None:
            self._emit_sheetbook_commit(p, display_path=str(display_path))
            self._release_sheetbook_plan_segments(p, workflow_node_id=str(node_id), release_reason="commit")
            return

        final_path = str(export_path)
        staging_path = self._staging_path_for_final_output(final_path)

        try:
            workbook_cls = _get_openpyxl_workbook_class()
        except ImportError as exc:
            raise ScalimWorkflowWriteError(str(exc)) from exc

        wb = workbook_cls(write_only=True)
        try:
            _write_sheetbook_plan_to_openpyxl_workbook(wb, p)
            _save_openpyxl_workbook_atomic(wb, output_path=staging_path)
        except Exception:
            _best_effort_close_write_only_workbook_worksheets(wb)
            raise
        finally:
            with suppress(Exception):
                wb.close()

        self._register_staged_output(
            resource_type="sheetbook",
            resource_id=p.resource_id,
            workflow_node_id=str(node_id),
            staged_path=str(staging_path),
            final_path=str(final_path),
        )
        self._release_sheetbook_plan_segments(p, workflow_node_id=str(node_id), release_reason="commit")

    @override
    def _discard_sheetbook(self, plan: object, *, workflow_node_id: str, reason: str) -> None:
        p = cast("_SheetBookPlan", plan)  # pragma: allow-cast sheetbook plan typed narrowing
        node_id = p.last_workflow_node_id or str(workflow_node_id)
        display_path = p.export_path if p.export_path is not None else "<memory>"
        self._emit_resource_discard(
            workflow_node_id=node_id,
            resource_type="sheetbook",
            resource_id=p.resource_id,
            path=str(display_path),
            reason=str(reason),
        )
        self._release_sheetbook_plan_segments(p, workflow_node_id=str(node_id), release_reason="discard")

    def _release_sheetbook_plan_segments(self, plan: "_SheetBookPlan", *, workflow_node_id: str, release_reason: str) -> None:
        for sheet_plan in plan.sheets.values():
            for seg in sheet_plan.segments:
                seg.rows = []
            sheet_plan.segments = []
            sheet_plan.cell_count = 0
        plan.total_cells = 0
        display_path = plan.export_path if plan.export_path is not None else "<memory>"
        self._log_plan_segment_release(
            workflow_node_id=str(workflow_node_id),
            resource_type="sheetbook",
            resource_id=plan.resource_id,
            path=str(display_path),
            release_reason=str(release_reason),
        )
        _ = self._sheetbooks.pop(str(plan.resource_id), None)


__all__ = (
    "SheetBookDef",
    "SheetBookPlan",
    "SheetBookSegment",
    "SheetBookSheetPlan",
    "WorkflowSheetBookResourceMixin",
)

SheetBookPlan = _SheetBookPlan
SheetBookSegment = _SheetBookSegment
SheetBookSheetPlan = _SheetBookSheetPlan
WorkflowSheetBookResourceMixin = _WorkflowSheetBookResourceMixin
