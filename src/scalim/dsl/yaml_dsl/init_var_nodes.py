from typing import Any, Dict, Optional, Union

from ...exceptions import ScalimYamlError
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from ...vendor.dataclassesx import field as dataclass_field


class ScalimInitVarNodeValueError(ScalimYamlError):
    path: str
    reason: str

    def __init__(self, reason: str, *, path: str) -> None:
        super().__init__(reason)
        self.path = path
        self.reason = reason

    @override
    def __str__(self) -> str:
        return "{} {}".format(self.path, self.reason)


class ScalimInitVarNodeTypeError(ScalimYamlError):
    path: str
    reason: str

    def __init__(self, reason: str, *, path: str) -> None:
        super().__init__(reason)
        self.path = path
        self.reason = reason

    @override
    def __str__(self) -> str:
        return "{} {}".format(self.path, self.reason)


_INIT_VAR_KEY = "$init_var"


@dataclass(frozen=True)
class InitVarRef:
    """内部路径节点: `{$init_var: <name>}` 的显式表示."""

    name: str
    path: str = dataclass_field(compare=False)


PathNode = Union[str, InitVarRef]
OptionalPathNode = Optional[PathNode]


def parse_init_var_mapping_node(raw: Dict[str, Any], *, path: str) -> str:
    """校验并解析 `{$init_var: <name>}` 指令节点,返回归一化后的变量名.

    说明:
    - 这里只校验指令节点的结构(是否为单键 `mapping`,是否包含 `$init_var`,值是否为非空字符串).
    - 运行时解析(例如检查 `init_vars` 是否包含该变量)由调用方处理.
    """

    extra_keys = sorted([str(k) for k in raw if k != _INIT_VAR_KEY])
    if extra_keys:
        msg = "only supports {{{}: <name>}}; unexpected keys: {}".format(_INIT_VAR_KEY, ", ".join(extra_keys))
        raise ScalimInitVarNodeValueError(msg, path=path)

    # 注意: `{ $init_var: null }` 与 `{}` 语义不同.
    # - `{}`: 缺少 `$init_var` 键,属于“结构/形状”错误
    # - `null`: 键存在但值非法,属于“值类型”错误
    if _INIT_VAR_KEY not in raw:
        msg = "only supports {{{}: <name>}}; missing '{}'".format(_INIT_VAR_KEY, _INIT_VAR_KEY)
        raise ScalimInitVarNodeValueError(msg, path=path)

    init_var_raw = raw.get(_INIT_VAR_KEY)
    if not isinstance(init_var_raw, str) or not init_var_raw.strip():
        reason = "must be a non-empty string"
        raise ScalimInitVarNodeTypeError(reason, path="{}.{}".format(path, _INIT_VAR_KEY))

    return init_var_raw.strip()


def parse_init_var_ref(raw: Dict[str, Any], *, path: str) -> InitVarRef:
    """校验并解析 `{$init_var: <name>}` 指令节点,返回显式 `InitVarRef`."""

    name = parse_init_var_mapping_node(raw, path=path)
    return InitVarRef(name=str(name), path=str(path))


__all__ = (
    "InitVarRef",
    "OptionalPathNode",
    "PathNode",
    "ScalimInitVarNodeTypeError",
    "ScalimInitVarNodeValueError",
    "parse_init_var_mapping_node",
    "parse_init_var_ref",
)
