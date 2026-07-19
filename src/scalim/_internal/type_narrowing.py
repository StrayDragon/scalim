# pragma: allow-cast-file 运行时类型窄化辅助函数
from typing import Any, Dict, List, Mapping, Optional, cast

from ..typedefs import RuntimeValue


def as_mapping(value: RuntimeValue, *, path: str = "") -> Optional[Dict[str, Any]]:
    """
    将 `value` 尝试窄化为配置类映射(`dict`).

    说明: 该模块属于运行时边界,只做轻量 `isinstance` 检查,并把必要的 `cast(...)` 收敛到这里,
    避免在业务逻辑中分散重复的 `cast()`/窄化片段.
    """

    _ = path
    if not isinstance(value, dict):
        return None
    return cast("Dict[str, Any]", value)


def as_list(value: RuntimeValue, *, path: str = "") -> Optional[List[Any]]:
    """
    将 `value` 尝试窄化为配置类列表(`list`).

    说明: 与 `as_mapping` 相同,该函数主要用于在运行时边界做轻量窄化,
    并让上层业务逻辑不必反复书写 `isinstance + cast`.
    """

    _ = path
    if not isinstance(value, list):
        return None
    return cast("List[Any]", value)


def require_str(value: RuntimeValue, *, path: str) -> str:
    """要求 `value` 在 `path` 处为 `str`; 否则抛出 `TypeError`(消息口径稳定)."""

    if isinstance(value, str):
        return value
    msg = "{} must be a string, got '{}'".format(path, type(value).__name__)
    raise TypeError(msg)


def mapping_get_str(mapping: Mapping[str, Any], key: str, *, path: str) -> Optional[str]:
    """从映射读取可选的 `str` 字段; 若字段存在但类型不为 `str` 则抛出 `TypeError`."""

    if key not in mapping:
        return None
    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    msg = "{}.{} must be a string, got '{}'".format(path, key, type(value).__name__)
    raise TypeError(msg)


__all__ = ()
