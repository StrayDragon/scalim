"""`workflow` 共享输出资源(稳定导入路径).

说明:
- 本文件对外保持稳定导入路径;具体实现拆分到同目录的 `workflow_resources_*` 子模块
- 运行时需兼容 `Python 3.6`
"""

from ....sinks.sink_base import create_temp_path
from ....vendor.compact.importlibx import require_optional_dependency
from .workflow_resources_base import WRITE_LOCK_SUFFIX, WorkflowWriteError, acquire_write_lock, release_write_lock
from .workflow_resources_csv import WorkflowCsvResourceMixin, read_csv_header
from .workflow_resources_sheetbook import SheetBookDef, WorkflowSheetBookResourceMixin
from .workflow_resources_workbook import WorkflowWorkbookResourceMixin, best_effort_close_write_only_workbook_worksheets

# 兼容: 测试/内部点位仍在引用旧的私有符号名.
_WRITE_LOCK_SUFFIX = WRITE_LOCK_SUFFIX
_acquire_write_lock = acquire_write_lock
_release_write_lock = release_write_lock
_read_csv_header = read_csv_header
_best_effort_close_write_only_workbook_worksheets = best_effort_close_write_only_workbook_worksheets


class WorkflowResourceManager(
    WorkflowWorkbookResourceMixin,
    WorkflowCsvResourceMixin,
    WorkflowSheetBookResourceMixin,
):
    """工作流级共享输出资源管理器(延迟提交 + 原子落盘)."""


__all__ = [
    "_WRITE_LOCK_SUFFIX",
    "SheetBookDef",
    "WorkflowResourceManager",
    "WorkflowWriteError",
    "_acquire_write_lock",
    "_best_effort_close_write_only_workbook_worksheets",
    "_read_csv_header",
    "_release_write_lock",
    "create_temp_path",
    "require_optional_dependency",
]
