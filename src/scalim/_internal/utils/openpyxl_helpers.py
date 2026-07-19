"""`openpyxl` 写出辅助: `write_only` `worksheet` 关闭与原子保存.

供 `workflow` 资源与 `sinks` 的 `Excel` 实现共用,避免重复实现漂移.
运行时需兼容 `Python 3.6`.
"""

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from openpyxl.workbook import Workbook

from .atomic_paths import atomic_replace_temp_path, best_effort_remove_temp_path, create_temp_path


def best_effort_close_write_only_worksheet(worksheet: Any) -> None:
    """尽力关闭 `openpyxl` `write_only` 的 `worksheet`.

    避免异常路径下生成器在 `GC` 时对已关闭文件做 I/O.
    """

    try:
        is_closed = bool(worksheet.closed)
    except AttributeError:
        return
    if is_closed:
        return
    with suppress(Exception):
        worksheet.close()


def best_effort_close_write_only_workbook_worksheets(workbook: Any) -> None:
    """尽力关闭 `write_only workbook` 下所有 `worksheet`(异常路径使用)."""

    try:
        worksheets_obj = workbook.worksheets
    except AttributeError:
        return
    try:
        worksheets = list(worksheets_obj)
    except TypeError:
        return
    for ws in worksheets:
        best_effort_close_write_only_worksheet(ws)


def save_openpyxl_workbook_atomic(workbook: "Workbook", *, output_path: str) -> None:
    """将 `workbook` 保存到临时文件并原子替换到 `output_path`.

    失败时尽力清理临时文件,并重新抛出原始异常(由调用方包装领域错误).
    """

    wb = cast("Any", workbook)  # pragma: allow-cast openpyxl workbook runtime boundary
    temp_path = create_temp_path(output_path, ".xlsx.tmp")
    temp_obj = Path(temp_path)
    try:
        wb.save(temp_obj)
        atomic_replace_temp_path(temp_path, output_path)
    except Exception:
        best_effort_remove_temp_path(temp_path)
        raise


__all__ = ()
