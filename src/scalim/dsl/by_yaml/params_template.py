import re
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from ...spec.ir.binding import LoaderCallContextIr, build_stable_lookup_key_list
from ...typedefs import LoaderCallKwargs, RuntimeValue
from ...vendor.compact.typing_extensionsx import TypeGuard, override
from ...vendor.dataclassesx import dataclass

_RUNTIME_PREFIX = "$runtime."
_RUNTIME_VAR_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_DIRECTIVE_INIT_VAR = "$init_var"
_DIRECTIVE_RUNTIME = "$runtime"  # 旧写法: 已废弃,直接拒绝
_DIRECTIVE_KEYS = "$keys"
_DIRECTIVE_ROWS = "$rows"


class ParamsTemplateError(ValueError):
    """`params` 模板编译/渲染相关异常基类."""


class ParamsTemplateCompileError(ParamsTemplateError):
    message: str
    path: str

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message)
        self.message = message
        self.path = path

    @override
    def __str__(self) -> str:
        return "{} (path={})".format(self.message, self.path)


class ParamsTemplateRenderError(ParamsTemplateError):
    message: str
    path: str

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message)
        self.message = message
        self.path = path

    @override
    def __str__(self) -> str:
        return "{} (path={})".format(self.message, self.path)


def _path_child(path: str, key: object) -> str:
    if not path:
        return str(key)
    return "{}.{}".format(path, str(key))


def _path_index(path: str, idx: int) -> str:
    return "{}[{}]".format(path, idx)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _is_tuple(value: object) -> TypeGuard[Tuple[object, ...]]:
    return isinstance(value, tuple)


def _is_set(value: object) -> TypeGuard[Set[object]]:
    return isinstance(value, set)


def _deepcopy_literal(value: RuntimeValue) -> RuntimeValue:
    # 这里刻意只对常见容器做深拷贝,避免对任意对象进行 `deepcopy`.
    # `init_vars` 可能注入任意对象(例如 `datetime`/`Decimal` 等),应按“不透明字面值”透传.
    if _is_dict(value):
        copied: Dict[object, RuntimeValue] = {}
        for k, v in value.items():
            copied[k] = _deepcopy_literal(v)
        return copied
    if _is_list(value):
        return [_deepcopy_literal(v) for v in value]
    if _is_tuple(value):
        return tuple(_deepcopy_literal(v) for v in value)
    if _is_set(value):
        copied_set: Set[RuntimeValue] = set()
        for v in value:
            copied_set.add(_deepcopy_literal(v))
        return copied_set
    return value


# region typed template IR


@dataclass(frozen=True)
class _NodeBase:
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        del ctx, path
        raise NotImplementedError


@dataclass(frozen=True)
class LiteralNode(_NodeBase):
    value: RuntimeValue

    @override
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        _ = (ctx, path)
        return _deepcopy_literal(self.value)


@dataclass(frozen=True)
class MappingNode(_NodeBase):
    items: Tuple[Tuple[object, _NodeBase], ...]

    @override
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        out: Dict[object, RuntimeValue] = {}
        for k, node in self.items:
            out[k] = node.render(ctx, path=_path_child(path, k))
        return out


@dataclass(frozen=True)
class ListNode(_NodeBase):
    items: Tuple[_NodeBase, ...]

    @override
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        out: List[RuntimeValue] = []
        for idx, node in enumerate(self.items):
            out.append(node.render(ctx, path=_path_index(path, idx)))
        return out


@dataclass(frozen=True)
class KeysDirectiveNode(_NodeBase):
    as_: str

    @override
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        if not ctx.is_ref_loader or ctx.lookup_keys is None:
            msg = "`$keys` is only valid in ref loader call contexts"
            raise ParamsTemplateRenderError(msg, path=path)

        if self.as_ == "list":
            if ctx.lookup_keys_list is not None:
                return list(ctx.lookup_keys_list)
            return build_stable_lookup_key_list(ctx.lookup_keys)

        # `set` 模式
        return set(ctx.lookup_keys)


@dataclass(frozen=True)
class RowsDirectiveNode(_NodeBase):
    cache_mode: str

    @override
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        if not ctx.is_ref_loader or ctx.batch_rows is None:
            msg = "`$rows` is only valid in ref loader call contexts"
            raise ParamsTemplateRenderError(msg, path=path)
        return ctx.batch_rows


@dataclass(frozen=True)
class RuntimeDirectiveNode(_NodeBase):
    name: str

    @override
    def render(self, ctx: LoaderCallContextIr, *, path: str) -> RuntimeValue:
        _ = (ctx, path)
        msg = "`$init_var` directive must be resolved at compile time; provide init_vars when compiling the params template"
        raise ParamsTemplateRenderError(msg, path=path)


Node = Union[LiteralNode, MappingNode, ListNode, RuntimeDirectiveNode, KeysDirectiveNode, RowsDirectiveNode]


@dataclass(frozen=True)
class CompiledParamsTemplate:
    root: Node
    directive_mode: str = "none"
    keys_as: str = "set"
    rows_cache_mode: str = "batch"

    def is_empty_mapping(self) -> bool:
        if not isinstance(self.root, MappingNode):
            return False
        return not self.root.items

    def render_kwargs(self, ctx: LoaderCallContextIr, *, path: str) -> LoaderCallKwargs:
        rendered = self.root.render(ctx, path=path)
        if rendered is None:
            return {}
        if not _is_dict(rendered):
            msg = "params template must render to a mapping"
            raise ParamsTemplateRenderError(msg, path=path)

        typed: LoaderCallKwargs = {}
        for key, value in rendered.items():
            if not isinstance(key, str):
                msg = "params template mapping keys must be strings"
                raise ParamsTemplateRenderError(msg, path=_path_child(path, key))
            typed[key] = value
        return typed


# endregion


@dataclass(frozen=True)
class _CompileOptions:
    init_vars: Optional[Mapping[str, RuntimeValue]]
    allow_keys: bool
    allow_rows: bool


@dataclass
class _CompileState:
    directive_mode: str = "none"
    keys_as: str = "set"
    rows_cache_mode: str = "batch"

    def seen_keys(self, as_: str, *, path: str) -> None:
        if self.directive_mode == "rows":
            msg = "`$keys` and `$rows` are mutually exclusive"
            raise ParamsTemplateCompileError(msg, path=path)
        if self.directive_mode == "none":
            self.directive_mode = "keys"
            self.keys_as = as_
            return
        if self.keys_as != as_:
            msg = "Conflicting `$keys.as` options in the same template"
            raise ParamsTemplateCompileError(msg, path=path)

    def seen_rows(self, cache_mode: str, *, path: str) -> None:
        if self.directive_mode == "keys":
            msg = "`$keys` and `$rows` are mutually exclusive"
            raise ParamsTemplateCompileError(msg, path=path)
        if self.directive_mode == "none":
            self.directive_mode = "rows"
            self.rows_cache_mode = cache_mode
            return
        if self.rows_cache_mode != cache_mode:
            msg = "Conflicting `$rows.cache_mode` options in the same template"
            raise ParamsTemplateCompileError(msg, path=path)


def _maybe_compile_runtime_literal(
    node_value: object,
    *,
    node_path: str,
) -> None:
    if not isinstance(node_value, str):
        return
    if not node_value.startswith(_RUNTIME_PREFIX):
        return

    var_name = node_value[len(_RUNTIME_PREFIX) :]
    if not var_name:
        msg = "Legacy `$runtime.<name>` placeholder is not supported; use `{$init_var: <name>}`"
        raise ParamsTemplateCompileError(msg, path=node_path)
    if not _RUNTIME_VAR_RE.match(var_name):
        msg = "Legacy `$runtime.<name>` placeholder is not supported; invalid init var name '{}' (expected [a-zA-Z_][a-zA-Z0-9_]*)".format(
            var_name
        )
        raise ParamsTemplateCompileError(msg, path=node_path)

    msg = "Legacy `$runtime.{}` placeholder is not supported; use `{{$init_var: {}}}`".format(var_name, var_name)
    raise ParamsTemplateCompileError(msg, path=node_path)


def _compile_legacy_runtime_directive_node(
    mapping_dict: Dict[object, object],
    *,
    node_path: str,
) -> Node:
    var_name_raw = mapping_dict.get(_DIRECTIVE_RUNTIME)
    if isinstance(var_name_raw, str) and var_name_raw and _RUNTIME_VAR_RE.match(var_name_raw):
        msg = "Legacy `{{$runtime: {}}}` directive is not supported; migrate to `{{$init_var: {}}}`".format(var_name_raw, var_name_raw)
        raise ParamsTemplateCompileError(msg, path=node_path)

    msg = "Legacy `{$runtime: <name>}` directive is not supported; migrate to `{$init_var: <name>}`"
    raise ParamsTemplateCompileError(msg, path=node_path)


def _compile_runtime_directive_node(
    mapping_dict: Dict[object, object],
    *,
    node_path: str,
    opts: _CompileOptions,
    resolve_runtime: bool,
) -> Node:
    var_name_raw = mapping_dict.get(_DIRECTIVE_INIT_VAR)
    if not isinstance(var_name_raw, str) or not var_name_raw:
        msg = "`$init_var` value must be a non-empty string"
        raise ParamsTemplateCompileError(msg, path=_path_child(node_path, _DIRECTIVE_INIT_VAR))
    if not _RUNTIME_VAR_RE.match(var_name_raw):
        msg = "`$init_var` value '{}' is invalid (expected [a-zA-Z_][a-zA-Z0-9_]*)".format(var_name_raw)
        raise ParamsTemplateCompileError(msg, path=_path_child(node_path, _DIRECTIVE_INIT_VAR))

    if resolve_runtime:
        if opts.init_vars is None or var_name_raw not in opts.init_vars:
            msg = "Missing init var: {}".format(var_name_raw)
            raise ParamsTemplateCompileError(msg, path=node_path)
        return LiteralNode(opts.init_vars[var_name_raw])

    return RuntimeDirectiveNode(name=var_name_raw)


def _compile_keys_directive_node(
    mapping_dict: Dict[object, object],
    *,
    node_path: str,
    opts: _CompileOptions,
    state: _CompileState,
) -> Node:
    if not opts.allow_keys:
        msg = "`$keys` is not allowed in this context"
        raise ParamsTemplateCompileError(msg, path=node_path)
    options_raw = mapping_dict.get(_DIRECTIVE_KEYS)
    as_mode = _parse_keys_options(options_raw, path=_path_child(node_path, _DIRECTIVE_KEYS))
    state.seen_keys(as_mode, path=node_path)
    return KeysDirectiveNode(as_=as_mode)


def _compile_rows_directive_node(
    mapping_dict: Dict[object, object],
    *,
    node_path: str,
    opts: _CompileOptions,
    state: _CompileState,
) -> Node:
    if not opts.allow_rows:
        msg = "`$rows` is not allowed in this context"
        raise ParamsTemplateCompileError(msg, path=node_path)
    options_raw = mapping_dict.get(_DIRECTIVE_ROWS)
    cache_mode = _parse_rows_options(options_raw, path=_path_child(node_path, _DIRECTIVE_ROWS))
    state.seen_rows(cache_mode, path=node_path)
    return RowsDirectiveNode(cache_mode=cache_mode)


def _maybe_compile_directive_node(
    mapping_dict: Dict[object, object],
    *,
    node_path: str,
    opts: _CompileOptions,
    state: _CompileState,
    resolve_runtime: bool,
) -> Optional[Node]:
    directive_key: Optional[str] = None
    if _DIRECTIVE_INIT_VAR in mapping_dict:
        directive_key = _DIRECTIVE_INIT_VAR
    elif _DIRECTIVE_RUNTIME in mapping_dict:
        directive_key = _DIRECTIVE_RUNTIME
    elif _DIRECTIVE_KEYS in mapping_dict:
        directive_key = _DIRECTIVE_KEYS
    elif _DIRECTIVE_ROWS in mapping_dict:
        directive_key = _DIRECTIVE_ROWS
    else:
        return None

    if len(mapping_dict) != 1:
        msg = "Directive node must be a single-key mapping: `{}`, `{}` or `{}`".format(
            _DIRECTIVE_INIT_VAR, _DIRECTIVE_KEYS, _DIRECTIVE_ROWS
        )
        raise ParamsTemplateCompileError(msg, path=node_path)

    if directive_key == _DIRECTIVE_RUNTIME:
        return _compile_legacy_runtime_directive_node(mapping_dict, node_path=node_path)
    if directive_key == _DIRECTIVE_INIT_VAR:
        return _compile_runtime_directive_node(mapping_dict, node_path=node_path, opts=opts, resolve_runtime=resolve_runtime)
    if directive_key == _DIRECTIVE_KEYS:
        return _compile_keys_directive_node(mapping_dict, node_path=node_path, opts=opts, state=state)
    return _compile_rows_directive_node(mapping_dict, node_path=node_path, opts=opts, state=state)


def _compile_mapping_node(
    mapping_dict: Dict[object, object],
    *,
    node_path: str,
    opts: _CompileOptions,
    state: _CompileState,
    resolve_runtime: bool,
) -> MappingNode:
    mapping_items: List[Tuple[object, Node]] = []
    for k, v in mapping_dict.items():
        mapping_items.append(
            (
                k,
                _compile_params_template_node(
                    v,
                    node_path=_path_child(node_path, k),
                    opts=opts,
                    state=state,
                    resolve_runtime=resolve_runtime,
                ),
            )
        )
    return MappingNode(items=tuple(mapping_items))


def _compile_list_node(
    list_value: Sequence[object],
    *,
    node_path: str,
    opts: _CompileOptions,
    state: _CompileState,
    resolve_runtime: bool,
) -> ListNode:
    list_items: List[Node] = []
    for idx, item in enumerate(list_value):
        list_items.append(
            _compile_params_template_node(
                item,
                node_path=_path_index(node_path, idx),
                opts=opts,
                state=state,
                resolve_runtime=resolve_runtime,
            )
        )
    return ListNode(items=tuple(list_items))


def _compile_params_template_node(
    node_value: object,
    *,
    node_path: str,
    opts: _CompileOptions,
    state: _CompileState,
    resolve_runtime: bool,
) -> Node:
    _maybe_compile_runtime_literal(node_value, node_path=node_path)

    if _is_dict(node_value):
        mapping_dict = node_value
        directive_node = _maybe_compile_directive_node(
            mapping_dict,
            node_path=node_path,
            opts=opts,
            state=state,
            resolve_runtime=resolve_runtime,
        )
        if directive_node is not None:
            return directive_node
        return _compile_mapping_node(
            mapping_dict,
            node_path=node_path,
            opts=opts,
            state=state,
            resolve_runtime=resolve_runtime,
        )

    if _is_list(node_value):
        return _compile_list_node(
            node_value,
            node_path=node_path,
            opts=opts,
            state=state,
            resolve_runtime=resolve_runtime,
        )

    return LiteralNode(node_value)


def compile_params_template(
    value: object,
    *,
    path: str,
    init_vars: Optional[Mapping[str, RuntimeValue]] = None,
    resolve_runtime: bool = True,
    allow_keys: bool = True,
    allow_rows: bool = True,
) -> CompiledParamsTemplate:
    """将加载器 `params` 模板编译为类型化的 `IR`.

    说明:
    - `{$init_var: <name>}` 在编译期解析并落成不透明的 `LiteralNode`(后续不会再按结构扫描其内部内容).
    - `$keys`/`$rows` 为保留指令节点,仅允许以“单键字典”形式出现.
    - 编译后的模板渲染是纯函数: 不会原地修改 `YAML` 解析对象(避免锚点/别名共享对象被污染).
    """

    opts = _CompileOptions(init_vars=init_vars, allow_keys=allow_keys, allow_rows=allow_rows)
    state = _CompileState()
    root = _compile_params_template_node(value, node_path=path, opts=opts, state=state, resolve_runtime=resolve_runtime)
    return CompiledParamsTemplate(
        root=root,
        directive_mode=state.directive_mode,
        keys_as=state.keys_as,
        rows_cache_mode=state.rows_cache_mode,
    )


def _parse_keys_options(options_raw: object, *, path: str) -> str:
    if options_raw is None:
        return "set"
    if not _is_dict(options_raw):
        msg = "`$keys` options must be a mapping or null"
        raise ParamsTemplateCompileError(msg, path=path)
    options = options_raw
    for k in options:
        if str(k) != "as":
            msg = "Unknown `$keys` option: {}".format(str(k))
            raise ParamsTemplateCompileError(msg, path=_path_child(path, k))
    raw_as = options.get("as")
    if raw_as is None:
        return "set"
    if not isinstance(raw_as, str):
        msg = "`$keys.as` must be a string"
        raise ParamsTemplateCompileError(msg, path=_path_child(path, "as"))
    if raw_as not in {"set", "list"}:
        msg = "`$keys.as` must be one of: set, list"
        raise ParamsTemplateCompileError(msg, path=_path_child(path, "as"))
    return raw_as


def _parse_rows_options(options_raw: object, *, path: str) -> str:
    if options_raw is None:
        return "batch"
    if not _is_dict(options_raw):
        msg = "`$rows` options must be a mapping or null"
        raise ParamsTemplateCompileError(msg, path=path)
    options = options_raw
    for k in options:
        if str(k) != "cache_mode":
            msg = "Unknown `$rows` option: {}".format(str(k))
            raise ParamsTemplateCompileError(msg, path=_path_child(path, k))
    raw_cache = options.get("cache_mode")
    if raw_cache is None:
        return "batch"
    if not isinstance(raw_cache, str):
        msg = "`$rows.cache_mode` must be a string"
        raise ParamsTemplateCompileError(msg, path=_path_child(path, "cache_mode"))
    if raw_cache not in {"batch", "none"}:
        msg = "`$rows.cache_mode` must be one of: batch, none"
        raise ParamsTemplateCompileError(msg, path=_path_child(path, "cache_mode"))
    return raw_cache


__all__ = [
    "CompiledParamsTemplate",
    "ParamsTemplateCompileError",
    "ParamsTemplateError",
    "ParamsTemplateRenderError",
    "compile_params_template",
]
