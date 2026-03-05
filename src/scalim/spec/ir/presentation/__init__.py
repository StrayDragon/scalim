from dataclasses import dataclass, field
from typing import Dict, Optional

from ....typedefs import FieldPresentationKind


@dataclass(frozen=True)
class CsvFieldPresentationIr:
    """
    CSV展示配置(IR): 定义CSV输出的格式参数
    """

    delimiter: Optional[str] = None
    """
    字段分隔符
    """

    encoding: Optional[str] = None
    """
    文件编码
    """


@dataclass(frozen=True)
class SpreadsheetFieldPresentationIr:
    """
    电子表格展示配置(IR): 定义 `Excel` 等电子表格输出的样式参数
    """

    number_format: Optional[str] = None
    """
    数字格式 (如 "#,##0.00")
    """

    bold: Optional[bool] = None
    """
    是否加粗
    """

    italic: Optional[bool] = None
    """
    是否斜体
    """

    font_color: Optional[str] = None
    """
    字体颜色(例如 `#FF0000`).
    """

    fill_color: Optional[str] = None
    """
    填充颜色(例如 `#FFFF00`).
    """

    alignment: Optional[str] = None
    """
    对齐方式(例如 `left`、`center`、`right`).
    """

    width: Optional[int] = None
    """
    列宽
    """

    wrap: Optional[bool] = None
    """
    是否自动换行
    """


@dataclass(frozen=True)
class PandasFieldPresentationIr:
    """
    `pandas` 展示配置(IR): 定义 `pandas.DataFrame` 输出的类型参数
    """

    dtype: Optional[str] = None
    """
    数据类型(例如 `int64`、`float64`、`str`).
    """

    category: Optional[bool] = None
    """
    是否转换为分类类型
    """


@dataclass(frozen=True)
class FieldPresentationIr:
    """
    字段展示配置(IR): 定义字段在各种输出格式下的展示方式
    """

    kind: FieldPresentationKind = "generic"
    """
    展示类型(`generic`/`csv`/`excel`/`pandas`).
    """

    label: Optional[str] = None
    """
    显示标签 (覆盖字段名)
    """

    description: Optional[str] = None
    """
    字段描述
    """

    csv: Optional[CsvFieldPresentationIr] = None
    """
    CSV专用配置
    """

    excel: Optional[SpreadsheetFieldPresentationIr] = None
    """
    `Excel` 专用配置
    """

    pandas: Optional[PandasFieldPresentationIr] = None
    """
    `pandas` 专用配置
    """


@dataclass(frozen=True)
class ExportProfileIr:
    """
    导出配置(IR): 定义数据导出的全局配置,包括默认展示和字段级覆盖
    """

    name: str = ""
    """
    配置名称
    """

    default_presentation: Optional[FieldPresentationIr] = None
    """
    默认展示配置 (应用于所有字段)
    """

    field_overrides: Dict[str, FieldPresentationIr] = field(default_factory=dict)
    """
    字段级覆盖配置(`field_id` -> `FieldPresentationIr`).
    """


__all__ = [
    "CsvFieldPresentationIr",
    "ExportProfileIr",
    "FieldPresentationIr",
    "PandasFieldPresentationIr",
    "SpreadsheetFieldPresentationIr",
]
