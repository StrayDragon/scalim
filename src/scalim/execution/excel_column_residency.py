"""列式 `Excel` 文件写出驻留策略(`Python` `SSOT`).

仅当 `OutputSpec.format=excel` 且 `streaming=False` 时生效.
`YAML` `books` / `output_composition` 为行写出,不得用本枚举假装切换.
"""

from ..vendor.compact import StrEnum


class ExcelColumnResidency(StrEnum):
    """列式 `Excel` 文件 `sink` 驻留策略."""

    HOLD = "hold"
    WINDOW = "window"


__all__ = ("ExcelColumnResidency",)
