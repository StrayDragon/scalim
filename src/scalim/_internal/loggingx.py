"""`scalim` 内部日志工具.

目标:
- 仅依赖标准库 `logging`(可在任意模块安全导入).
- 不做全局配置: 不安装 `handler`/`formatter`, 不修改 `root logger`.
- 提供一致的日志前缀与稳定的 `k=v` 格式化,便于人读与检索.
"""

import json
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..vendor.compact.typing_extensionsx import TypeGuard

_SCALIM_ROOT_LOGGER_NAME = "scalim"


def _ensure_null_handler(logger: logging.Logger) -> None:
    # 作为库代码: 避免出现 `No handler could be found...` 之类警告,同时不主动配置用户侧 `logging`.
    if any(isinstance(h, logging.NullHandler) for h in logger.handlers):
        return
    logger.addHandler(logging.NullHandler())


_ensure_null_handler(logging.getLogger(_SCALIM_ROOT_LOGGER_NAME))


def get_logger(subsystem: str = "") -> logging.Logger:
    """返回稳定的 `scalim.*` 命名空间下的 `logging.Logger`."""

    subsystem_text = str(subsystem or "").strip()
    if subsystem_text:
        return logging.getLogger("{}.{}".format(_SCALIM_ROOT_LOGGER_NAME, subsystem_text))
    return logging.getLogger(_SCALIM_ROOT_LOGGER_NAME)


def prefix(subsystem: str) -> str:
    """生成用户可见的日志前缀(不依赖用户侧 `formatter`)."""

    subsystem_text = str(subsystem or "").strip()
    if not subsystem_text:
        return "[scalim] "
    return "[scalim] {}: ".format(subsystem_text)


def _is_list_or_tuple(value: object) -> TypeGuard[Iterable[object]]:
    return isinstance(value, (list, tuple))


def _is_set(value: object) -> TypeGuard[Iterable[object]]:
    return isinstance(value, set)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


def _stringify_value(value: Any) -> str:
    if _is_list_or_tuple(value):
        return ",".join(str(x) for x in value)
    if _is_set(value):
        items = [str(x) for x in value]
        items.sort()
        return ",".join(items)
    if _is_dict(value):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        except TypeError:
            return str(value)
    return str(value)


def format_kv(mapping: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> str:
    """将键值对格式化为稳定的 `k=v, k2=v2` 文本.

    - 键会按字典序排序,保证稳定输出.
    - 值为 `None` 的条目会被忽略.
    """

    items: Dict[str, Any] = {}
    if mapping:
        for key, value in mapping.items():
            items[str(key)] = value
    for key, value in kwargs.items():
        items[str(key)] = value

    parts: List[str] = []
    for key in sorted(items.keys()):
        value = items[key]
        if value is None:
            continue
        parts.append("{}={}".format(key, _stringify_value(value)))
    return ", ".join(parts)


def bind(logger: logging.Logger, **context: Any) -> "logging.LoggerAdapter[logging.Logger]":
    """通过 `logging.LoggerAdapter` 绑定上下文,便于用户侧 `formatter` 引用字段."""

    return logging.LoggerAdapter(logger, context)


__all__ = ()
