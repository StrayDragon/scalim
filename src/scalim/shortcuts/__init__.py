"""`shortcuts` 稳定门面入口.

该命名空间用于承载面向用户的快捷门面,避免用户材料/下游集成手写内部协议细节.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import resources  # noqa: TC004

__all__ = ("resources",)
