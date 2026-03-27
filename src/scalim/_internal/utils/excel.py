from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def escape_excel_formula(value: Any, *, allow_formulas: bool) -> Any:
    """对 `Excel` 公式前缀做转义(通过在原始字符串前追加 `'`).

    规则:
    - 仅对 `str` 生效
    - `allow_formulas=True` 时原样返回
    - 以 `'` 开头的字符串视为已转义,保持不变
    - 通过 `value.lstrip()` 检测前导空白后的首字符
    """

    if allow_formulas:
        return value
    if not isinstance(value, str) or not value:
        return value
    if value.startswith("'"):
        return value
    stripped = value.lstrip()
    if stripped and stripped[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value


__all__ = []
