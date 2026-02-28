# region imports

import math
from collections.abc import Callable, Hashable, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, cast

# endregion

ConvertibleToInt = int | float | str | bytes
"""可转换为 `int` 的类型"""

ConvertibleToStr = int | float | str | bytes | bool
"""可转换为 `str` 的类型"""

ConvertibleToIntTuple = tuple[ConvertibleToInt, ...] | list[ConvertibleToInt] | Sequence[ConvertibleToInt]
"""可转换为 `int` 元组的类型"""

SeparatedValues = str | int | float
"""CSV 字符串或已转换的值"""


class NamedLookupCast:
    """用于 `lookup_cast` 标注的可调用包装器，提供稳定的名称。"""

    scales_lookup_cast_name: str

    def __init__(self, name: str, fn: Callable[[Any], Hashable | None]) -> None:
        self.scales_lookup_cast_name = name
        self._fn: Callable[[Any], Hashable | None] = fn

    def __call__(self, value: Any) -> Hashable | None:
        return self._fn(value)


def to_int(value: ConvertibleToInt) -> int:
    """转换为 `int`: 会抛异常哦!"""
    return int(value)


def to_str(value: ConvertibleToStr) -> str:
    """转换为 `str`: 会抛异常哦!"""
    return str(value)


def to_int_tuple(value: ConvertibleToIntTuple) -> tuple[int, ...]:
    """将序列的每个元素转换为 `int`: 会抛异常哦!"""
    return tuple(int(v) for v in value)


def get_seps_values_first_int(value: object, sep: str = ",") -> int:
    """从分割字符串提取第一个值并转换为 `int`: 会抛异常哦!"""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        first = value.split(sep)[0].strip()
        if not first:
            msg = f"Empty first value in CSV string: {value!r}"
            raise ValueError(msg)
        return int(first)
    msg = f"Unsupported type for CSV conversion: {type(value).__name__}"
    raise TypeError(msg)


def must_to_int(value: Any) -> int | None:
    """强制转换为 `int`: 抑制异常,异常时为 `None`"""
    if value is None:
        return None
    try:
        # `cast()` 用于满足静态检查,同时保持运行时行为不变.
        return int(cast("ConvertibleToInt", value))
    except (ValueError, TypeError):
        return None


def must_to_str(value: Any) -> str | None:
    """强制转换为 `str`: 抑制异常,异常时为 `None`"""
    if value is None:
        return None
    return str(value)


def must_to_int_tuple(value: ConvertibleToIntTuple | None) -> tuple[int, ...] | None:
    """强制将序列的每个元素转换为 `int`: 抑制异常,异常时为 `None`"""
    if value is None:
        return None
    if not isinstance(value, (tuple, list)):
        return None
    try:
        return tuple(int(v) for v in value)
    except (ValueError, TypeError):
        return None


def must_get_seps_values_first_int(value: object | None, sep: str = ",") -> int | None:
    """强制从分割字符串提取第一个值并转换为 `int`: 抑制异常,异常时为 `None`"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    first = value.split(sep)[0].strip()
    if not first:
        return None
    try:
        return int(first)
    except ValueError:
        return None


def _format_decimal_no_exponent(d: Decimal) -> str:
    """格式化 `Decimal` 为字符串,去除尾部零和科学计数法"""
    sign, digits, exponent = d.as_tuple()
    if exponent in {"n", "N", "F"}:
        return str(d)

    exponent_int = int(exponent)  # type: ignore[arg-type]
    digit_str = "".join(str(digit) for digit in digits)

    if exponent_int >= 0:
        result = digit_str + "0" * exponent_int
    else:
        abs_exp = abs(exponent_int)
        if abs_exp >= len(digit_str):
            result = "0." + "0" * (abs_exp - len(digit_str)) + digit_str
        else:
            result = digit_str[:-abs_exp] + "." + digit_str[-abs_exp:]
        result = result.rstrip("0").rstrip(".")

    if sign:
        result = "-" + result

    return result or "0"


def auto_str_normalize(value: Any) -> str | None:  # noqa: C901, PLR0911, PLR0912
    """将值规范化为稳定的字符串形式,用于关联键匹配

    规则:
    - `None`/`NaN`: 返回 `None`
    - `int`: 直接转字符串
    - `float`: 去除尾部零 (例如 `123.0 -> "123"`, `123.45 -> "123.45"`)
    - `Decimal`: 去除尾部零,禁用科学计数法
    - `datetime`: ISO 8601 格式 `YYYY-MM-DD HH:MM:SS`
    - `date`: ISO 8601 格式 `YYYY-MM-DD`
    - `time`: ISO 8601 格式 `HH:MM:SS`
    - `str`: 保持原样
    - 其他类型: 返回 `None` (转换失败)
    """
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        int_value = int(value)
        if value == float(int_value):
            return str(int_value)
        return format(value, ".15g")

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            return None
        return _format_decimal_no_exponent(value)

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    if isinstance(value, str):
        return value

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None

    return None


def auto_normalize_key(value: Any) -> Hashable | None:  # noqa: PLR0911
    """自动规范化关联键,尝试类型转换后回退到 `auto_str_normalize`

    策略:
    1. `None`/`NaN`: 返回 `None`
    2. 尝试保持原始类型 (`int`/`str`)
    3. 对于复杂类型,回退到 `auto_str_normalize`
    """
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        # `float` 键存在歧义,需要显式 `lookup_cast`/`value_cast`.
        return None

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, str)):
        return value

    if isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            return None
        try:
            int_val = int(value)
            if value == int_val:
                return int_val
        except (ValueError, OverflowError):
            pass
        return auto_str_normalize(value)

    return auto_str_normalize(value)
