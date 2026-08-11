"""文件写出布局策略(`Python` `SSOT`).

闭集 `OutputWriteLayout` 统一解释行流式 / 列 `HOLD` / 列 `WINDOW`.
未设置时由 `OutputSpec.streaming` + `ExcelColumnResidency` 推导,行为与历史工厂一致.
`YAML` 编写面不得声明本枚举或等价字段.
"""

from typing import Optional

from ..vendor.compact import StrEnum
from .excel_column_residency import ExcelColumnResidency


class OutputWriteLayout(StrEnum):
    """文件 `sink` 写出布局(闭集)."""

    ROW_STREAM = "row_stream"
    COLUMN_HOLD = "column_hold"
    COLUMN_WINDOW = "column_window"


def resolve_output_write_layout(
    *,
    output_write_layout: Optional[OutputWriteLayout],
    streaming: bool,
    output_format: str,
    excel_column_residency: ExcelColumnResidency,
    has_output_composition: bool = False,
) -> OutputWriteLayout:
    """解析生效的 `layout`.

    优先级:显式 `output_write_layout` > 推导 > 默认.
    推导表见 `runtime-output-write-layout` / `c30` `design`.
    """
    if output_write_layout is not None:
        if not isinstance(output_write_layout, OutputWriteLayout):
            msg = "output_write_layout must be an OutputWriteLayout"
            raise TypeError(msg)
        return output_write_layout

    if has_output_composition:
        return OutputWriteLayout.ROW_STREAM

    fmt = (output_format or "csv").lower()
    if streaming:
        # 历史:`excel` + `WINDOW` + `streaming` 在工厂 `fail-fast`;此处仍推导 `row_stream`,
        # 由 `validate_output_write_layout_combos` / 工厂保留同等拒绝.
        return OutputWriteLayout.ROW_STREAM

    if fmt == "excel" and excel_column_residency is ExcelColumnResidency.WINDOW:
        return OutputWriteLayout.COLUMN_WINDOW

    # `csv` 忽略 `residency`(含 `WINDOW`)→ `column_hold`,与今日 `_create_file_sink` 一致.
    return OutputWriteLayout.COLUMN_HOLD


def validate_output_write_layout_combos(
    *,
    layout: OutputWriteLayout,
    output_format: str,
    streaming: bool,
    excel_column_residency: ExcelColumnResidency,
    has_output_composition: bool,
    layout_explicit: bool,
) -> None:
    """互斥组合 `fail-fast`(文案可诊断;禁止静默降级)."""
    fmt = (output_format or "csv").lower()

    if has_output_composition and layout is not OutputWriteLayout.ROW_STREAM:
        msg = (
            "`OutputWriteLayout.{}` 与 `output_composition`(`YAML` books/多输出行组合)互斥."
            " 组合层仅为行流式写出;列布局只适用于非 `composition` 的列式 `IR` 文件 `sink`."
            " 请改用 `row_stream`/`HOLD`,或改用手写列式 `sink` / 非 `composition` 路径."
        ).format(layout.value)
        raise ValueError(msg)

    if has_output_composition and excel_column_residency is ExcelColumnResidency.WINDOW:
        msg = (
            "`ExcelColumnResidency.WINDOW` 与 `output_composition`(`YAML` books/多输出行组合)互斥."
            " 组合层仅为行流式写出;`WINDOW` 只适用于列式 `IR` 文件 `sink`"
            "(`format=excel` 且 `streaming=False`)."
            " 请改用 `HOLD`,或改用手写 `StreamingColumnExcelSink` / 非 `composition` 列式路径."
        )
        raise ValueError(msg)

    if layout is OutputWriteLayout.COLUMN_WINDOW and fmt != "excel":
        msg = (
            "`OutputWriteLayout.column_window` 仅适用于 `format=excel` 列式文件 `sink`;"
            " 当前 format={!r}. `CSV` 无 `WINDOW` 实现;请改用 `column_hold`/`row_stream`,"
            " 或改用 `excel`."
        ).format(fmt)
        raise ValueError(msg)

    # 未设 `layout` 时保留历史:`excel` `WINDOW` 不得与行式 `streaming` 并存.
    if not layout_explicit and fmt == "excel" and streaming and excel_column_residency is ExcelColumnResidency.WINDOW:
        msg = (
            "`ExcelColumnResidency.WINDOW` 仅适用于列式 `Excel` 文件 `sink`"
            "(`OutputSpec.format=excel` 且 `streaming=False`)."
            " 当前为行式写出(`streaming=True`);请改用 `HOLD`,或关闭 `streaming` 后再设 `WINDOW`."
        )
        raise ValueError(msg)


__all__ = (
    "OutputWriteLayout",
    "resolve_output_write_layout",
    "validate_output_write_layout_combos",
)
