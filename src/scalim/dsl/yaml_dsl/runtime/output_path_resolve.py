import os
from pathlib import Path
from typing import Any, Dict, Optional

from ..init_var_nodes import InitVarRef, OptionalPathNode


def resolve_output_container_path(
    raw: OptionalPathNode,
    *,
    init_vars: Optional[Dict[str, Any]],
    path: str,
) -> str:
    """解析输出资源路径节点为非空字符串路径.

    支持:
    - 静态字符串路径.
    - `{$init_var: <name>}` 映射节点,从 `init_vars` 中解析.

    说明:
    - 相对路径按原样返回(由调用方决定是否归一化).
    - 错误信息尽量稳定且可诊断,便于测试断言.
    """

    if isinstance(raw, dict):
        msg = "{} must be a string path or InitVarRef".format(path)
        raise TypeError(msg)

    if isinstance(raw, InitVarRef):
        var_name = str(raw.name)
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


def resolve_yaml_relative_output_path(
    raw: OptionalPathNode,
    *,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    path: str,
) -> str:
    """解析路径并将相对路径按 `base_dir` 归一化为绝对路径.

    用于:
    - `resources.files.*.csv_file.path`
    - `resources.books.*.xlsx_file.path`
    - `resources.books.*.xlsx_memory.export_xlsx.path`

    约束:
    - `raw` 支持静态字符串与 `{$init_var: <name>}` 指令节点
    - 相对路径解析基准为声明该路径的 YAML 文件所在目录(`base_dir`)
    """

    raw_path = resolve_output_container_path(raw, init_vars=init_vars, path=path)
    p = Path(str(raw_path)).expanduser()
    if not p.is_absolute():
        p = Path(str(base_dir)) / p
    return str(p.resolve(strict=False))


__all__ = (
    "resolve_output_container_path",
    "resolve_yaml_relative_output_path",
)
