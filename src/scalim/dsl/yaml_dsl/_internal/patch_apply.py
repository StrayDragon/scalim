"""`YAML DSL` 的配置 `patch`/`overlay` 合并辅助函数(内部 `SSOT`).

说明:
- 仅用于内部配置 `patch`/`overlay` 的合并与校验,不属于对外 `API`
- 运行时需兼容 `Python 3.6`
"""

from collections.abc import Mapping
from typing import Any, cast

from ..workflow import ScalimWorkflowConfigError

__all__ = ()


def assert_no_unknown_keys(patch: Mapping[str, Any], *, allowed_keys: set[str], path: str) -> None:
    unknown = sorted({str(k) for k in patch} - set(allowed_keys))
    if not unknown:
        return
    msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
    raise ScalimWorkflowConfigError(msg, path=path)


def as_opt_mapping(value: Any, *, path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        msg = f"{path} must be a mapping"
        raise ScalimWorkflowConfigError(msg, path=path)
    return cast("dict[str, Any]", value)  # pragma: allow-cast runtime overrides dict narrowing


def as_opt_str(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"{path} must be a string"
        raise ScalimWorkflowConfigError(msg, path=path)
    v = str(value).strip()
    return v or None


def as_required_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        msg = f"{path} must be a non-empty string"
        raise ScalimWorkflowConfigError(msg, path=path)
    v = str(value).strip()
    if not v:
        msg = f"{path} must be a non-empty string"
        raise ScalimWorkflowConfigError(msg, path=path)
    return v


def as_bool(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        msg = f"{path} must be a bool"
        raise ScalimWorkflowConfigError(msg, path=path)
    return bool(value)
