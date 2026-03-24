"""`workflow` 共享输出资源: `sheetbook` 实现(内部模块).

说明:
- 承载 `sheetbook_sheet`/`sheetbook_append` 的内存物化、读取与导出
- 运行时需兼容 `Python 3.6`
"""

from abc import ABC
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Iterator, List, Optional, Tuple, cast

from ....events.catalog import EVENT_DIAGNOSTIC_WARNING
from ....events.events import DiagnosticWarningEvent
from ....sinks.sink_base import create_temp_path
from ....utils.excel import escape_excel_formula
from ....vendor.compact.typing_extensionsx import override
from .workflow_resources_base import WorkflowResourceManagerBase, WorkflowWriteError, acquire_write_lock, release_write_lock
from .workflow_resources_csv import build_alignment_mapping, describe_header_diff, iter_csv_rows, read_csv_header
from .workflow_resources_workbook import best_effort_close_write_only_workbook_worksheets, get_openpyxl_workbook_class

# 内部实现仍沿用原有局部命名,减少重构噪音.
_build_alignment_mapping = build_alignment_mapping
_describe_header_diff = describe_header_diff
_iter_csv_rows = iter_csv_rows
_read_csv_header = read_csv_header
_best_effort_close_write_only_workbook_worksheets = best_effort_close_write_only_workbook_worksheets
_get_openpyxl_workbook_class = get_openpyxl_workbook_class


@dataclass(frozen=True)
class SheetBookDef:
    resource_id: str
    budget_max_sheets: int
    budget_max_total_cells: int
    export_path: Optional[str]
    export_write_lock: bool
    export_allow_formulas: bool = False


@dataclass
class _SheetBookSegment:
    producer_node_id: str
    start_row: int
    end_row: int
    header_policy: str


@dataclass
class _SheetBookSheetPlan:
    sheet: str
    baseline_header: List[str]
    columns: Dict[str, List[str]]
    segments: List[_SheetBookSegment]
    row_count: int = 0


@dataclass
class _SheetBookPlan:
    resource_id: str
    budget_max_sheets: int
    budget_max_total_cells: int
    export_path: Optional[str]
    export_write_lock: bool
    export_allow_formulas: bool
    sheet_order: List[str]
    sheets: Dict[str, _SheetBookSheetPlan]
    lock_path: Optional[Path] = None
    total_cells: int = 0
    last_workflow_node_id: Optional[str] = None


class _WorkflowSheetBookResourceMixin(WorkflowResourceManagerBase, ABC):
    def _get_or_create_sheetbook(self, sheetbook_id: str, *, workflow_node_id: str) -> _SheetBookPlan:
        key = str(sheetbook_id)
        with self._lock:
            existing = cast("Optional[_SheetBookPlan]", self._sheetbooks.get(key))
            if existing is not None:
                return existing

            raw_def = self._sheetbook_defs.get(key)
            if raw_def is None:
                msg = "Unknown sheetbook resource id: {!r}".format(key)
                raise WorkflowWriteError(msg)

            raw_def = cast("SheetBookDef", raw_def)
            plan = SheetBookPlan(
                resource_id=str(raw_def.resource_id),
                budget_max_sheets=int(raw_def.budget_max_sheets),
                budget_max_total_cells=int(raw_def.budget_max_total_cells),
                export_path=str(raw_def.export_path) if raw_def.export_path is not None else None,
                export_write_lock=bool(raw_def.export_write_lock),
                export_allow_formulas=bool(raw_def.export_allow_formulas),
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
        if allow_over_budget:  # pragma: no cover
            return  # pragma: no cover
        limit = int(plan.budget_max_total_cells)
        if int(new_total_cells) <= limit:
            return
        diff = [
            "budget.max_total_cells={}".format(limit),
            "new_total_cells={}".format(int(new_total_cells)),
        ]
        msg = "Sheetbook budget exceeded: sheetbook={!r}".format(str(plan.resource_id))
        raise WorkflowWriteError(msg, diff=diff)

    def apply_sheetbook_sheet(  # noqa: C901
        self,
        *,
        workflow_node_id: str,
        sheetbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv_path: str,
        on_conflict: str,
    ) -> None:
        plan = self._get_or_create_sheetbook(sheetbook_id, workflow_node_id=str(workflow_node_id))
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
                    msg = "Sheet conflict (sheetbook_sheet): sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name)
                    raise WorkflowWriteError(msg, diff=["on_conflict=error", "existing_sheet=present"])
                if on_conflict == "overwrite":
                    action = "overwrite"
            elif len(plan.sheets) >= int(plan.budget_max_sheets):
                msg = "Sheetbook budget exceeded: max_sheets (sheetbook={!r})".format(str(sheetbook_id))
                diff = [
                    "budget.max_sheets={}".format(int(plan.budget_max_sheets)),
                    "current_sheets={}".format(len(plan.sheets)),
                    "new_sheet={!r}".format(sheet_name),
                ]
                raise WorkflowWriteError(msg, diff=diff)

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

        # 读取并物化到内存(列式),用于下游读取与导出.
        col_lists: List[List[str]] = [[] for _ in expected]
        for row in _iter_csv_rows(input_csv_path):
            for col_idx, src_idx in enumerate(mapping):
                col_lists[col_idx].append(row[src_idx] if src_idx >= 0 and src_idx < len(row) else "")

        columns: Dict[str, List[str]] = {str(key): col_lists[idx] for idx, key in enumerate(expected)}
        row_count = len(col_lists[0]) if col_lists else 0
        new_sheet_cells = int(row_count) * len(expected)

        with self._lock:
            existing = plan.sheets.get(sheet_name)
            old_cells = 0
            if existing is not None:
                old_cells = int(existing.row_count) * len(existing.baseline_header)

            new_total = int(plan.total_cells) - int(old_cells) + int(new_sheet_cells)
            self._check_sheetbook_budget(plan, new_total_cells=new_total)

            if existing is None:
                plan.sheet_order.append(sheet_name)

            sheet_plan = _SheetBookSheetPlan(
                sheet=sheet_name,
                baseline_header=list(expected),
                columns=columns,
                segments=[],
                row_count=int(row_count),
            )
            sheet_plan.segments.append(
                _SheetBookSegment(
                    producer_node_id=str(input_node_id),
                    start_row=0,
                    end_row=int(row_count),
                    header_policy="once",
                )
            )
            plan.sheets[sheet_name] = sheet_plan
            plan.total_cells = int(new_total)
            plan.last_workflow_node_id = str(workflow_node_id)

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

    def apply_sheetbook_append(  # noqa: C901, PLR0912, PLR0915
        self,
        *,
        workflow_node_id: str,
        sheetbook_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv_path: str,
        align_by: str,
        header_policy: str,
        on_mismatch: str,
    ) -> None:
        plan = self._get_or_create_sheetbook(sheetbook_id, workflow_node_id=str(workflow_node_id))
        sheet_name = str(sheet)
        input_header = _read_csv_header(input_csv_path)

        pending_warning: Optional[DiagnosticWarningEvent] = None
        pending_warning_meta: Optional[Dict[str, object]] = None
        pending_skip = False
        start_row = 0

        with self._lock:
            sheet_plan = plan.sheets.get(sheet_name)
            if sheet_plan is None:
                if len(plan.sheets) >= int(plan.budget_max_sheets):
                    msg = "Sheetbook budget exceeded: max_sheets (sheetbook={!r})".format(str(sheetbook_id))
                    diff = [
                        "budget.max_sheets={}".format(int(plan.budget_max_sheets)),
                        "current_sheets={}".format(len(plan.sheets)),
                        "new_sheet={!r}".format(sheet_name),
                    ]
                    raise WorkflowWriteError(msg, diff=diff)
                plan.sheet_order.append(sheet_name)
                sheet_plan = _SheetBookSheetPlan(sheet=sheet_name, baseline_header=list(input_header), columns={}, segments=[], row_count=0)
                plan.sheets[sheet_name] = sheet_plan

            expected = list(sheet_plan.baseline_header)
            mapping = _build_alignment_mapping(expected, input_header)

            mismatch = False
            if str(align_by) == "field_id":
                exp_set = {str(x) for x in expected}
                act_set = {str(x) for x in input_header}
                missing = exp_set.difference(act_set)
                extra = act_set.difference(exp_set)
                mismatch = bool(missing or extra)
            else:
                mismatch = list(input_header) != expected

            if mismatch:
                diff = _describe_header_diff(expected, input_header)
                if on_mismatch == "error":
                    msg = "Field alignment mismatch (sheetbook_append): sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name)
                    raise WorkflowWriteError(msg, diff=diff)
                if on_mismatch == "warn":
                    pending_warning = DiagnosticWarningEvent(
                        message="Field alignment mismatch (warn): sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name),
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
                # 重复写入检测: 同一生产者不应写入同一工作表多次.
                for seg in sheet_plan.segments:
                    if str(seg.producer_node_id) == str(input_node_id):
                        msg = "Duplicate sheetbook write for the same producer: sheetbook={!r}, sheet={!r}, producer={!r}".format(
                            str(sheetbook_id),
                            sheet_name,
                            str(input_node_id),
                        )
                        raise WorkflowWriteError(msg, diff=["producer_node_id={!r}".format(str(input_node_id))])

                start_row = int(sheet_plan.row_count)

        if pending_warning is not None:
            _ = self._instrumentation.emit(EVENT_DIAGNOSTIC_WARNING, pending_warning, meta=pending_warning_meta)

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

        # 读取并对齐到基线表头(列式追加).
        col_lists: List[List[str]] = [[] for _ in expected]
        for row in _iter_csv_rows(input_csv_path):
            for col_idx, src_idx in enumerate(mapping):
                col_lists[col_idx].append(row[src_idx] if src_idx >= 0 and src_idx < len(row) else "")

        append_rows = len(col_lists[0]) if col_lists else 0
        append_cells = int(append_rows) * len(expected)

        with self._lock:
            sheet_plan = plan.sheets.get(sheet_name)
            if sheet_plan is None:  # pragma: no cover
                msg = "Sheetbook sheet missing during append: sheetbook={!r}, sheet={!r}".format(str(sheetbook_id), sheet_name)
                raise WorkflowWriteError(msg)

            new_total = int(plan.total_cells) + int(append_cells)
            self._check_sheetbook_budget(plan, new_total_cells=new_total)

            for idx, field_key in enumerate(expected):
                col = sheet_plan.columns.get(field_key)
                if col is None:
                    col = []
                    sheet_plan.columns[str(field_key)] = col
                col.extend(col_lists[idx])

            sheet_plan.row_count = int(sheet_plan.row_count) + int(append_rows)
            sheet_plan.segments.append(
                _SheetBookSegment(
                    producer_node_id=str(input_node_id),
                    start_row=int(start_row),
                    end_row=int(start_row) + int(append_rows),
                    header_policy=str(header_policy),
                )
            )
            plan.total_cells = int(new_total)
            plan.last_workflow_node_id = str(workflow_node_id)

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

    def iter_sheetbook_sheet_rows(  # noqa: C901
        self,
        *,
        consumer_node_id: str,
        visible_producer_node_ids: FrozenSet[str],
        producer_node_id: str,
        sheetbook_id: str,
        sheet: str,
    ) -> Iterator[Dict[str, object]]:
        """读取 `sheetbook` 的行快照(按 `ref.node` 截断;按依赖可见性过滤).

        返回: `Iterator[Dict[str, object]]`, 每行必须为 `JSON-like mapping`.
        """
        _ = str(consumer_node_id)
        producer = str(producer_node_id)
        sb_id = str(sheetbook_id)
        sheet_name = str(sheet)
        visible = frozenset(str(x) for x in visible_producer_node_ids)

        with self._lock:
            plan = cast("Optional[_SheetBookPlan]", self._sheetbooks.get(sb_id))
            if plan is None:
                msg = "Unknown sheetbook resource id: {!r}".format(sb_id)
                raise ValueError(msg)
            sheet_plan = plan.sheets.get(sheet_name)
            if sheet_plan is None:
                msg = "Unknown sheetbook sheet: sheetbook={!r}, sheet={!r}".format(sb_id, sheet_name)
                raise ValueError(msg)

            cutoff_idx = None
            for idx, seg in enumerate(sheet_plan.segments):
                if str(seg.producer_node_id) == producer:
                    cutoff_idx = int(idx)
                    break
            if cutoff_idx is None:
                msg = "Unknown sheetbook ref node for sheet: node={!r}, sheetbook={!r}, sheet={!r}".format(producer, sb_id, sheet_name)
                raise ValueError(msg)

            baseline_header = list(sheet_plan.baseline_header)
            columns = dict(sheet_plan.columns)
            segments: List[Tuple[str, int, int]] = []
            for seg in sheet_plan.segments[: cutoff_idx + 1]:
                seg_producer = str(seg.producer_node_id)
                if seg_producer != producer and seg_producer not in visible:
                    continue
                segments.append((seg_producer, int(seg.start_row), int(seg.end_row)))

        def _iter() -> Iterator[Dict[str, object]]:
            for _seg_producer, start, end in segments:
                for row_idx in range(int(start), int(end)):
                    row: Dict[str, object] = {}
                    for key in baseline_header:
                        col = columns.get(str(key))
                        if col is None:  # pragma: no cover
                            row[str(key)] = ""  # pragma: no cover
                            continue  # pragma: no cover
                        row[str(key)] = col[row_idx] if row_idx >= 0 and row_idx < len(col) else ""
                    yield row

        return _iter()

    @override
    def _commit_sheetbook(self, plan: object) -> None:  # noqa: C901, PLR0912, PLR0915
        p = cast("_SheetBookPlan", plan)
        export_path = p.export_path
        display_path = export_path if export_path is not None else "<memory>"
        if export_path is None:
            node_id = p.last_workflow_node_id or "__wf__commit"
            self._emit_resource_commit(
                workflow_node_id=node_id, resource_type="sheetbook", resource_id=p.resource_id, path=str(display_path)
            )
            return

        output_path = str(export_path)
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        lock_path = None
        if bool(p.export_write_lock):
            lock_path = acquire_write_lock(output_path)
            p.lock_path = lock_path

        try:
            workbook_cls = _get_openpyxl_workbook_class()
        except ImportError as exc:
            if lock_path is not None:
                release_write_lock(lock_path)
                p.lock_path = None
            raise WorkflowWriteError(str(exc)) from exc

        wb = workbook_cls(write_only=True)
        try:
            for sheet_name in p.sheet_order:
                sheet_plan = p.sheets.get(sheet_name)
                if sheet_plan is None:
                    continue  # pragma: no cover
                ws = wb.create_sheet(str(sheet_name))
                header_written = False
                fields = list(sheet_plan.baseline_header)
                escaped_fields = [escape_excel_formula(x, allow_formulas=bool(p.export_allow_formulas)) for x in fields]
                for seg in sheet_plan.segments:
                    if seg.header_policy == "always" or (seg.header_policy == "once" and not header_written):
                        _ = ws.append(list(escaped_fields))
                        header_written = True
                    # `never`: 不输出表头

                    for row_idx in range(int(seg.start_row), int(seg.end_row)):
                        out_row: List[object] = []
                        for field_key in fields:
                            col = sheet_plan.columns.get(str(field_key))
                            value = col[row_idx] if col is not None and row_idx >= 0 and row_idx < len(col) else ""
                            out_row.append(escape_excel_formula(value, allow_formulas=bool(p.export_allow_formulas)))
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
                msg = "Sheetbook export failed: {}: {}".format(type(exc).__name__, exc)
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
        self._emit_resource_commit(workflow_node_id=node_id, resource_type="sheetbook", resource_id=p.resource_id, path=str(display_path))

    @override
    def _discard_sheetbook(self, plan: object, *, workflow_node_id: str, reason: str) -> None:
        p = cast("_SheetBookPlan", plan)
        if p.lock_path is not None:
            release_write_lock(p.lock_path)
            p.lock_path = None
        node_id = p.last_workflow_node_id or str(workflow_node_id)
        display_path = p.export_path if p.export_path is not None else "<memory>"
        self._emit_resource_discard(
            workflow_node_id=node_id,
            resource_type="sheetbook",
            resource_id=p.resource_id,
            path=str(display_path),
            reason=str(reason),
        )


__all__ = [
    "SheetBookDef",
    "SheetBookPlan",
    "SheetBookSegment",
    "SheetBookSheetPlan",
    "WorkflowSheetBookResourceMixin",
    "_SheetBookPlan",
    "_SheetBookSegment",
    "_SheetBookSheetPlan",
    "_WorkflowSheetBookResourceMixin",
]

SheetBookPlan = _SheetBookPlan
SheetBookSegment = _SheetBookSegment
SheetBookSheetPlan = _SheetBookSheetPlan
WorkflowSheetBookResourceMixin = _WorkflowSheetBookResourceMixin
