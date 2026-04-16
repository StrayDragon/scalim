"""资源类 `shortcuts` 的稳定入口.

`v1` 子域:
- `outputs`: 从输出根目录发现最新一次发布的产物快照.
"""

# pragma: scalim-public-api tier1:140:scalim.shortcuts.resources|资源类 shortcut 稳定入口|从 output root 定位产物/资源
# pragma: scalim-public-api tier1:150:scalim.shortcuts.resources.outputs|outputs discovery facade|定位最新一次发布的 workbook/books 与 files

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import outputs  # noqa: TC004

__all__ = ("outputs",)
