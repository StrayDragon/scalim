"""资源类 `shortcuts` 的稳定入口.

`v1` 子域:
- `outputs`: 从输出根目录发现最新一次发布的产物快照.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import outputs  # noqa: TC004

__all__ = ("outputs",)
