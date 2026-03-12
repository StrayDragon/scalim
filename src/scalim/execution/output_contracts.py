from __future__ import absolute_import

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ExportLayout:
    """与 `DSL` 无关的导出布局.

    此对象定义:
    - 需要导出的字段(及其顺序)
    - 与字段顺序对齐的可选表头名称
    """

    field_ids: Tuple[str, ...]
    header_names: Optional[Tuple[str, ...]] = None

    def __post_init__(self) -> None:
        if self.header_names is not None and len(self.header_names) != len(self.field_ids):
            msg = "ExportLayout.header_names must align with field_ids"
            raise ValueError(msg)


@dataclass(frozen=True)
class OutputSpec:
    """与 `DSL` 无关的输出策略.

    当 `path` 为假值(`None`/`\"\"`)时,不会创建文件输出端.

    安全提示:
    - `path` 控制文件系统写入(会创建父目录并以原子方式替换目标文件).
    - 仅在 `YAML`/配置输入可信时启用基于文件的输出;否则应在外部校验/覆盖 `path`.
    """

    format: str = "csv"
    path: Optional[str] = None
    encoding: str = "utf-8"
    streaming: bool = True
    include_header: bool = True
    sheet_name: Optional[str] = None
    excel_allow_formulas: bool = False
    write_lock: bool = False


__all__ = [
    "ExportLayout",
    "OutputSpec",
]
