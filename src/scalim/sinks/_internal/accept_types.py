"""`Sink` 细胞类型接受约束与 `opt-in` 预检(`Python` `SSOT`).

- `FieldValue` / `FIELD_VALUE_TYPES` 为内建 `Excel` 推荐闭集参考.
- `CSV` 语义:任意 `object`,写出时 `str` 规范化(`accept` 恒真).
- 默认不预检;启用后在 `sink` 写出前 `fail-fast`.
"""

from typing import Callable, Optional

from ...typedefs import FIELD_VALUE_TYPES, CellValue, RuntimeValue, format_field_value_expected_types
from ...vendor.compact import StrEnum


class SinkTypePrecheck(StrEnum):
    """写出前按 `sink` `accept set` 做类型预检."""

    OFF = "off"
    ON = "on"


def require_sink_type_precheck(type_precheck: RuntimeValue, *, where: str) -> SinkTypePrecheck:
    """公开 `API` 运行时门禁:仅接受 `SinkTypePrecheck`(注解之外的字符串字面量 `fail-fast`)."""
    if not isinstance(type_precheck, SinkTypePrecheck):
        msg = "{0} must be a SinkTypePrecheck".format(where)
        raise TypeError(msg)
    return type_precheck


def is_excel_accepted_cell(value: CellValue) -> bool:
    """`Excel`/`openpyxl` 推荐可写集合(与 `FieldValue` 对齐;不声称接受 `np.datetime64`)."""
    if value is None:
        return True
    return isinstance(value, FIELD_VALUE_TYPES)


def is_csv_accepted_cell(value: CellValue) -> bool:
    """`CSV` 路径接受任意细胞(写出时字符串化)."""
    _ = value
    return True


def ensure_sink_accepted_cell(
    value: CellValue,
    *,
    field_id: str,
    sink_name: str,
    accepted: Callable[[CellValue], bool],
    expected_label: Optional[str] = None,
) -> CellValue:
    """`opt-in` 预检:不接受则 `TypeError`(含 `field`/`type`/`sink`)."""
    if accepted(value):
        return value
    expected = expected_label if expected_label is not None else format_field_value_expected_types()
    msg = "sink type precheck failed: sink={!r}, field_id={!r}, type={!r}, expected {}".format(
        sink_name,
        str(field_id),
        type(value).__name__,
        expected,
    )
    raise TypeError(msg)


__all__ = ()
