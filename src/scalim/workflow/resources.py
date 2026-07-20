"""`workflow` 共享输出资源(稳定导入路径).

说明:
- 本文件对外保持稳定导入路径;具体实现拆分到同目录的 `resources_*` 子模块
- 运行时需兼容 `Python 3.6`
- `book` 身份以 `defs` 成员关系表达(`pathful`→`workbook_defs`; `pathless`→`sheetbook_defs`)
"""

from typing import Any, FrozenSet, Iterator, Mapping, Optional, Tuple

from .resources_base import ScalimWorkflowWriteError
from .resources_csv import WorkflowCsvResourceMixin
from .resources_sheetbook import SheetBookDef, WorkflowSheetBookResourceMixin
from .resources_workbook import WorkflowWorkbookResourceMixin
from .tabular_artifacts import WorkflowTabularInput


class WorkflowResourceManager(
    WorkflowWorkbookResourceMixin,
    WorkflowCsvResourceMixin,
    WorkflowSheetBookResourceMixin,
):
    """工作流级共享输出资源管理器(延迟提交 + 原子落盘)."""

    def has_xlsx_book(self, book_id: str) -> bool:
        """是否为已注册的 `pathful`/`pathless` `xlsx` `book`(`workbook_defs` 或 `sheetbook_defs`)."""

        bid = str(book_id)
        return bid in self._workbook_defs or bid in self._sheetbook_defs

    def apply_book_sheet(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        book_id: str,
        sheet: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowTabularInput,
        on_conflict: str,
        export_header: Optional[Tuple[str, ...]] = None,
    ) -> None:
        bid = str(book_id)
        if bid in self._workbook_defs:
            return self.apply_workbook_sheet(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                workbook_id=bid,
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                export_header=export_header,
                on_conflict=str(on_conflict or "error"),
            )
        if bid in self._sheetbook_defs:
            return self.apply_sheetbook_sheet(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                sheetbook_id=bid,
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                export_header=export_header,
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
        input_csv: WorkflowTabularInput,
        align_by: str,
        header_policy: str,
        on_mismatch: str,
        export_header: Optional[Tuple[str, ...]] = None,
    ) -> None:
        bid = str(book_id)
        if bid in self._workbook_defs:
            return self.apply_workbook_append(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                workbook_id=bid,
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                export_header=export_header,
                align_by=str(align_by or "field_id"),
                header_policy=str(header_policy or "once"),
                on_mismatch=str(on_mismatch or "error"),
            )
        if bid in self._sheetbook_defs:
            return self.apply_sheetbook_append(
                workflow_node_id=str(workflow_node_id),
                decl_order=int(decl_order),
                sheetbook_id=bid,
                sheet=str(sheet),
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
                input_csv=input_csv,
                export_header=export_header,
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
    ) -> "Iterator[Mapping[str, Any]]":
        bid = str(book_id)
        if bid in self._sheetbook_defs:
            return self.iter_sheetbook_sheet_rows(
                consumer_node_id=str(consumer_node_id),
                visible_producer_node_ids=visible_producer_node_ids,
                producer_node_id=str(producer_node_id),
                sheetbook_id=bid,
                sheet=str(sheet),
            )
        if bid in self._workbook_defs:
            return self.iter_workbook_sheet_rows(
                consumer_node_id=str(consumer_node_id),
                visible_producer_node_ids=visible_producer_node_ids,
                producer_node_id=str(producer_node_id),
                workbook_id=bid,
                sheet=str(sheet),
            )
        msg = "book_sheet_rows only supports pathful/pathless books (book_id={!r})".format(str(book_id))
        raise ValueError(msg)


__all__ = (
    "ScalimWorkflowWriteError",
    "SheetBookDef",
    "WorkflowResourceManager",
)
