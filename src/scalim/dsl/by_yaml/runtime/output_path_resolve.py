import os
from typing import Any, Dict, Optional, cast

from ..init_var_nodes import parse_init_var_mapping_node


def resolve_output_container_path(
    raw: object,
    *,
    init_vars: Optional[Dict[str, object]],
    path: str,
) -> str:
    """解析 `OutputContainerConfig.path` 为非空字符串路径.

    支持:
    - 静态字符串路径.
    - `{$init_var: <name>}` 映射节点,从 `init_vars` 中解析.

    说明:
    - 相对路径按原样返回(由调用方决定是否归一化).
    - 错误信息尽量稳定且可诊断,便于测试断言.
    """

    if isinstance(raw, dict):
        var_name = parse_init_var_mapping_node(cast("Dict[str, Any]", raw), path=path)
        if init_vars is None or var_name not in init_vars:
            msg = "Missing init_var '{}' for {}".format(var_name, path)
            raise ValueError(msg)
        raw_value = init_vars[var_name]
        if raw_value is None:
            msg = "{} init_var '{}' resolved to None".format(path, var_name)
            raise ValueError(msg)
        if isinstance(raw_value, os.PathLike):
            resolved_raw = os.fspath(raw_value)
        elif isinstance(raw_value, str):
            resolved_raw = raw_value
        else:
            msg = "{} init_var '{}' must be str or os.PathLike, got {}".format(path, var_name, type(raw_value).__name__)
            raise TypeError(msg)

        resolved = str(resolved_raw).strip()
        if not resolved:
            msg = "{} init_var '{}' resolved to an empty string".format(path, var_name)
            raise ValueError(msg)
        return resolved

    if raw is None:
        msg = "{} is required".format(path)
        raise ValueError(msg)

    resolved = str(os.fspath(raw) if isinstance(raw, os.PathLike) else raw).strip()
    if not resolved:
        msg = "{} is required".format(path)
        raise ValueError(msg)
    return resolved


__all__ = [
    "resolve_output_container_path",
]
