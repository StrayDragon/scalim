from dataclasses import dataclass, field

from ....typedefs import FieldPresentationKind


@dataclass(frozen=True)
class CsvFieldPresentationIr:
    """
    CSV展示配置(IR): 定义CSV输出的格式参数
    """

    delimiter: str | None = None
    """
    字段分隔符
    """

    encoding: str | None = None
    """
    文件编码
    """


@dataclass(frozen=True)
class SpreadsheetFieldPresentationIr:
    """
    电子表格展示配置(IR): 定义 `Excel` 等电子表格输出的样式参数
    """

    number_format: str | None = None
    """
    数字格式 (如 "#,##0.00")
    """

    bold: bool | None = None
    """
    是否加粗
    """

    italic: bool | None = None
    """
    是否斜体
    """

    font_color: str | None = None
    """
    字体颜色(例如 `#FF0000`).
    """

    fill_color: str | None = None
    """
    填充颜色(例如 `#FFFF00`).
    """

    alignment: str | None = None
    """
    对齐方式(例如 `left`、`center`、`right`).
    """

    width: int | None = None
    """
    列宽
    """

    wrap: bool | None = None
    """
    是否自动换行
    """


@dataclass(frozen=True)
class PandasFieldPresentationIr:
    """
    `pandas` 展示配置(IR): 定义 `pandas.DataFrame` 输出的类型参数
    """

    dtype: str | None = None
    """
    数据类型(例如 `int64`、`float64`、`str`).
    """

    category: bool | None = None
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

    label: str | None = None
    """
    显示标签 (覆盖字段名)
    """

    description: str | None = None
    """
    字段描述
    """

    csv: CsvFieldPresentationIr | None = None
    """
    CSV专用配置
    """

    excel: SpreadsheetFieldPresentationIr | None = None
    """
    `Excel` 专用配置
    """

    pandas: PandasFieldPresentationIr | None = None
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

    default_presentation: FieldPresentationIr | None = None
    """
    默认展示配置 (应用于所有字段)
    """

    field_overrides: dict[str, FieldPresentationIr] = field(default_factory=dict)
    """
    字段级覆盖配置(`field_id` -> `FieldPresentationIr`).
    """


__all__ = (
    "CsvFieldPresentationIr",
    "ExportProfileIr",
    "FieldPresentationIr",
    "PandasFieldPresentationIr",
    "SpreadsheetFieldPresentationIr",
)
