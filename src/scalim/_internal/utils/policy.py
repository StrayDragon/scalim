"""封闭集合 `policy` 的边界辅助函数.

约定:
- 允许值集合的单一来源由调用方定义的 `Enum`/`StrEnum` 提供
- 配置/状态边界只接受内置 `str`(拒绝 `str` 子类)
- 归一化规则必须确定性,并基于 `Enum` 进行校验
- 返回值始终为内置 `str`(用于运行时存储与 `wire`/`state` 输出)
"""

from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

_E = TypeVar("_E", bound=Enum)


def _ensure_builtin_str(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        msg = f"{label} must be a str, got '{type(value).__name__}'"
        raise TypeError(msg)
    if type(value) is not str:
        msg = f"{label} must be a builtin str, got '{type(value).__name__}'"
        raise TypeError(msg)
    return value


def enum_values(enum_cls: type[_E]) -> tuple[str, ...]:
    values: list[str] = []
    for member in enum_cls:  # 迭代顺序与定义顺序一致
        value = member.value
        if type(value) is not str:
            msg = f"Enum {enum_cls.__name__} must use builtin str values, got '{type(value).__name__}'"
            raise TypeError(msg)
        values.append(value)
    return tuple(values)


def enum_values_label(enum_cls: type[_E], *, sep: str = "/") -> str:
    return sep.join(enum_values(enum_cls))


def parse_policy_value(
    enum_cls: type[_E],
    value: Any,
    *,
    label: str,
    default: _E | None = None,
    normalize: Callable[[str], str] | None = None,
    allow_empty: bool = False,
) -> str:
    """从配置/状态边界解析并校验 `policy`(封闭集合;快速失败).

    返回值为规范化后的内置 `str`(用于运行时存储).
    """
    if value is None:
        if default is None:
            msg = f"{label} must not be None; expected one of: {enum_values_label(enum_cls)}"
            raise TypeError(msg)
        return default.value

    raw = _ensure_builtin_str(value, label=label)
    normalized = raw
    if normalize is not None:
        normalized = normalize(raw)
    if not normalized:
        if allow_empty and default is not None:
            return default.value
        msg = f"{label} must not be empty; expected one of: {enum_values_label(enum_cls)}"
        raise ValueError(msg)

    try:
        member = enum_cls(normalized)
    except ValueError as exc:
        msg = f"Unknown {label}: {raw!r}; expected one of: {enum_values_label(enum_cls)}"
        raise ValueError(msg) from exc
    return member.value


def ensure_policy_enum(enum_cls: type[_E], value: Any, *, label: str) -> _E:
    """公开 `API`: 严格只接受 `Enum`(快速失败)."""
    if isinstance(value, enum_cls):
        return value
    msg = f"{label} must be a {enum_cls.__name__}; got '{type(value).__name__}'"
    raise TypeError(msg)


def normalize_token_lower_strip(value: str) -> str:
    return value.strip().lower()


def normalize_token_lower_strip_replace(value: str, *, old: str, new: str) -> str:
    return value.strip().lower().replace(old, new)


__all__ = ()
