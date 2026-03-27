"""`workflow` 共享输出资源(稳定导入路径).

说明:
- 本文件对外保持稳定导入路径;具体实现拆分到同目录的 `resources_*` 子模块
- 运行时需兼容 `Python 3.6`
"""

from .resources_base import ScalimWorkflowWriteError
from .resources_csv import WorkflowCsvResourceMixin
from .resources_sheetbook import SheetBookDef, WorkflowSheetBookResourceMixin
from .resources_workbook import WorkflowWorkbookResourceMixin


class WorkflowResourceManager(
    WorkflowWorkbookResourceMixin,
    WorkflowCsvResourceMixin,
    WorkflowSheetBookResourceMixin,
):
    """工作流级共享输出资源管理器(延迟提交 + 原子落盘)."""


__all__ = [
    "SheetBookDef",
    "WorkflowResourceManager",
    "ScalimWorkflowWriteError",
]
