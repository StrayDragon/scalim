"""`workflow` 共享输出资源(稳定导入路径).

说明:
- 本文件对外保持稳定导入路径;具体实现拆分到同目录的 `resources_*` 子模块
- 运行时需兼容 `Python 3.6`
"""

from typing import FrozenSet, Iterator, Mapping

from .resources_base import ScalimWorkflowWriteError
from .resources_csv import WorkflowCsvInput, WorkflowCsvResourceMixin
from .resources_sheetbook import SheetBookDef, WorkflowSheetBookResourceMixin
from .resources_workbook import WorkflowWorkbookResourceMixin


class WorkflowResourceManager(
    WorkflowWorkbookResourceMixin,
    WorkflowCsvResourceMixin,
    WorkflowSheetBookResourceMixin,
):
    """工作流级共享输出资源管理器(延迟提交 + 原子落盘)."""

    def _book_kind(self, book_id: str) -> str:
        bid = str(book_id)
        if bid in self._workbook_defs:
            return "xlsx_file"
        if bid in self._sheetbook_defs:
            return "xlsx_memory"
        return ""

    def apply_book_sheet(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        book_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowCsvInput,
        on_conflict: str,
    ) -> None:
        kind = self._book_kind(book_id)
        if kind == "xlsx_file":
            return self.apply_workbook_sheet(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                workbook_id=str(book_id),
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                on_conflict=str(on_conflict or "error"),
            )
        if kind == "xlsx_memory":
            return self.apply_sheetbook_sheet(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                sheetbook_id=str(book_id),
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                on_conflict=str(on_conflict or "error"),
            )
        msg = "Unknown book resource id: {!r}".format(str(book_id))
        raise ScalimWorkflowWriteError(msg)

    def apply_book_append(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        book_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowCsvInput,
        align_by: str,
        header_policy: str,
        on_mismatch: str,
    ) -> None:
        kind = self._book_kind(book_id)
        if kind == "xlsx_file":
            return self.apply_workbook_append(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                workbook_id=str(book_id),
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                align_by=str(align_by or "field_id"),
                header_policy=str(header_policy or "once"),
                on_mismatch=str(on_mismatch or "error"),
            )
        if kind == "xlsx_memory":
            return self.apply_sheetbook_append(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                sheetbook_id=str(book_id),
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                align_by=str(align_by or "field_id"),
                header_policy=str(header_policy or "once"),
                on_mismatch=str(on_mismatch or "error"),
            )
        msg = "Unknown book resource id: {!r}".format(str(book_id))
        raise ScalimWorkflowWriteError(msg)

    def iter_book_sheet_rows(
        self,
        *,
        consumer_node_id: str,
        visible_producer_node_ids: FrozenSet[str],
        producer_node_id: str,
        book_id: str,
        sheet: str,
    ) -> "Iterator[Mapping[str, object]]":
        kind = self._book_kind(book_id)
        if kind != "xlsx_memory":
            msg = "book_sheet_rows only supports xlsx_memory books (book_id={!r}, kind={!r})".format(str(book_id), kind or "<unknown>")
            raise ValueError(msg)
        return self.iter_sheetbook_sheet_rows(
            consumer_node_id=str(consumer_node_id),
            visible_producer_node_ids=visible_producer_node_ids,
            producer_node_id=str(producer_node_id),
            sheetbook_id=str(book_id),
            sheet=str(sheet),
        )


__all__ = [
    "ScalimWorkflowWriteError",
    "SheetBookDef",
    "WorkflowResourceManager",
]
