from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Tuple, cast

from ....typedefs import LoaderCallKwargs, LoaderCallParams, LookupKey, LookupKeyList, LookupKeySet, RowData
from ....vendor.compact.typing_extensionsx import TypeGuard
from ....vendor.dataclassesx import dataclass, field
from ..aliases import NormalizedLookupKeySpec
from ..callable_refs import CallableRefIr


def _is_tuple(value: object) -> TypeGuard[Tuple[object, ...]]:
    return isinstance(value, tuple)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


def _stable_lookup_key_sort_key(value: object) -> Tuple[str, object]:
    if _is_tuple(value):
        item_keys: List[Tuple[str, object]] = []
        for item in value:
            item_keys.append(_stable_lookup_key_sort_key(item))
        return ("tuple", tuple(item_keys))
    return (type(value).__name__, repr(value))


def build_stable_lookup_key_list(lookup_keys: LookupKeySet) -> LookupKeyList:
    """将 `lookup_keys` 稳定序列化为 `list`.

    用途:
    - `use_keys.as=list` 需要 `list` 容器形态;
    - `lookup_keys` 在执行路径中常以 `set` 去重,其迭代顺序受 `PYTHONHASHSEED` 影响;
    - 本函数提供确定性的输出顺序,提升回归可重复性与外部缓存命中可预测性.
    """

    return sorted(lookup_keys, key=_stable_lookup_key_sort_key)


@dataclass(frozen=True)
class LoaderCallContextIr:
    """
    加载器调用上下文(`IR`):框架在调用 `loader` 前构建此对象,并传递给用户的 `params_builder` 回调函数.
    """

    batch_row_nth: List[LookupKey] = field(default_factory=list)
    """
    当前批次的行号列表 (主源流的行索引)
    """

    source_id: str = ""
    """
    关联的数据源标识
    """

    field_keys: List[str] = field(default_factory=list)
    """
    需要从此加载器加载的字段列表
    """

    is_ref_loader: bool = False
    """
    是否为引用加载器(外键关联加载)
    """

    lookup_keys: Optional[LookupKeySet] = None
    """
    引用加载器的查找键集合(已去重)
    """

    lookup_keys_list: Optional[LookupKeyList] = None
    """
    引用加载器的查找键列表(由 `lookup_keys` 生成)
    """

    batch_rows: Optional[List[RowData]] = None
    """
    在 `rows` 模式下的当前批次行上下文(主源 + 已做关联合并)
    """


@dataclass(frozen=True)
class BindingIr:
    """参数绑定(`IR`):定义如何根据运行时上下文构建 `loader` 调用参数.

    说明:
    - `BindingIr` 只保存纯数据,不保存任何 `Python` 可调用对象.
    - 对 YAML DSL: 使用 `params_template`(由 params template 编译得到),执行期渲染为 `kwargs`.
    - 对 Python DSL: 使用 `params_builder_ref`(`CallableRefIr`),在“运行时链接”阶段解析为函数并注入 `RuntimeBindings.params_builders`.

    运行时 `params_builder` 的签名约定:
    - `(ctx: LoaderCallContextIr) -> (args, kwargs)`

    示例(运行时绑定引用):
    ```python
    BindingIr(
        key_field="order_id",
        params_builder_ref=PythonReferenceIr(
            reference="myapp.bindings:build_order_params",
            module_path="myapp.bindings",
            attr_path=("build_order_params",),
            style="dotted",
        ),
        param_name="order_ids",
    )
    ```
    """

    key_field: NormalizedLookupKeySpec
    """
    绑定的键字段名 (主键或外键)
    """

    params_template: Optional[object] = None
    """可选:编译后的参数模板对象(纯数据,不包含可调用对象).

    说明:
    - 对 YAML DSL: 来自 `scalim.dsl.yaml_dsl.params_template.compile_params_template`.
    - 该对象预期提供 `render_kwargs(ctx, path=...)` 方法.
    """

    params_builder_ref: Optional[CallableRefIr] = None
    """可选:运行时绑定的参数构造器引用(用于 `Python` DSL)."""

    mode: str = "keys"
    """
    绑定模式:`keys` 或 `rows`
    """

    as_: str = "set"
    """
    `keys` 模式下的容器形态:`set` 或 `list`
    """

    cache_mode: str = "none"
    """
    `rows` 模式缓存策略:`none` 或 `batch`.(`YAML`/`DSL` 未配置时,`rows` 默认 `batch`)
    """

    param_name: Optional[str] = None
    """
    `params_builder` 绑定的参数名(可选,用于诊断与签名稳定性)
    """

    template_path: str = ""
    """可选:模板路径标签(用于错误信息稳定)."""

    def __post_init__(self) -> None:
        if self.params_template is not None and self.params_builder_ref is not None:
            msg = "BindingIr must not set both params_template and params_builder_ref"
            raise ValueError(msg)

    def build_params(self, context: "LoaderCallContextIr") -> LoaderCallParams:
        """构建调用参数.

        注意:
        - 当使用 `params_builder_ref` 时,该方法无法直接构建参数(需要在“运行时链接”阶段解析为函数后,
          由执行阶段从 `RuntimeBindings` 获取并调用).
        """

        if self.params_builder_ref is not None:
            msg = "BindingIr(params_builder_ref=...) requires runtime linking; build_params is not available"
            raise TypeError(msg)
        template = self.params_template
        if template is None:
            return (), {}
        render = getattr(template, "render_kwargs", None)  # pragma: allow-dynattr optional-interface: params_template render contract
        if not callable(render):
            msg = "BindingIr.params_template must provide render_kwargs(ctx, path=...)"
            raise TypeError(msg)
        kwargs = cast(  # pragma: allow-cast params_template render kwargs contract boundary
            "LoaderCallKwargs",
            render(context, path=self.template_path or "(binding)"),  # type: ignore[misc]  # pragma: allow-any template typing boundary
        )
        return (), kwargs


def _empty_bindings() -> "Mapping[NormalizedLookupKeySpec, BindingIr]":
    return MappingProxyType({})


def _clone_bindings(bindings: Mapping[NormalizedLookupKeySpec, BindingIr]) -> Dict[NormalizedLookupKeySpec, BindingIr]:
    return dict(bindings)


def _is_valid_binding_key(value: object) -> bool:
    if isinstance(value, str):
        return True
    if _is_tuple(value):
        return all(isinstance(item, str) for item in value)
    return False


def _restore_bindings(bindings: object) -> Optional[Mapping[NormalizedLookupKeySpec, BindingIr]]:
    if not _is_dict(bindings):
        return None

    typed_bindings: Dict[NormalizedLookupKeySpec, BindingIr] = {}
    for key, value in bindings.items():
        if not _is_valid_binding_key(key):
            msg = "Invalid binding key in state: {!r}".format(key)
            raise TypeError(msg)
        if not isinstance(value, BindingIr):
            msg = "Invalid binding value in state for key {!r}".format(key)
            raise TypeError(msg)
        typed_key = cast("NormalizedLookupKeySpec", key)  # pragma: allow-cast runtime validated binding key type
        typed_bindings[typed_key] = value
    return MappingProxyType(typed_bindings)


@dataclass(frozen=True)
class LoaderIr:
    """
    [数据源]加载器(IR): 定义如何调用数据加载函数以及如何提取返回的数据
    """

    callable_ref: CallableRefIr
    """加载器可调用引用描述(纯数据,不包含可调用对象)."""

    extractor_ref: Optional[CallableRefIr] = None
    """可选:数据提取器可调用引用描述(纯数据,不包含可调用对象)."""

    bindings: Mapping[NormalizedLookupKeySpec, BindingIr] = field(default_factory=_empty_bindings)
    """
    参数绑定映射(`key_field` -> `Binding`).使用 `Mapping` 确保不可变性.
    """

    def __post_init__(self) -> None:
        if isinstance(self.bindings, dict):
            object.__setattr__(self, "bindings", MappingProxyType(_clone_bindings(self.bindings)))

    def __getstate__(self) -> Dict[str, object]:
        state = dict(self.__dict__)
        bindings = state.get("bindings")
        if isinstance(bindings, MappingProxyType):
            state["bindings"] = _clone_bindings(
                cast("Mapping[NormalizedLookupKeySpec, BindingIr]", bindings)  # pragma: allow-cast MappingProxyType typed narrowing
            )
        return state

    def __setstate__(self, state: Dict[str, object]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)
        bindings = _restore_bindings(state.get("bindings"))
        if bindings is not None:
            object.__setattr__(self, "bindings", bindings)

    def get_binding(self, key_field: NormalizedLookupKeySpec) -> Optional[BindingIr]:
        return self.bindings.get(key_field)


__all__ = (
    "BindingIr",
    "LoaderCallContextIr",
    "LoaderIr",
    "build_stable_lookup_key_list",
)
