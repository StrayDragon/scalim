from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Tuple, cast

from ....typedefs import LoaderCallParams, LookupKey, LookupKeyList, LookupKeySet, RowData
from ....vendor.compact.typing_extensionsx import TypeGuard
from ....vendor.dataclassesx import dataclass, field
from ..aliases import LoaderExtractor, LoaderParamsBuilder, LoaderResultMapCallable, NormalizedLookupKeySpec


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

    `params_builder` 用于构建调用参数,返回 `(args, kwargs)` 元组,例如:
    ```python
    lambda ctx: ((), {"order_ids": ctx.lookup_keys})
    ```

    示例:
    ```python
    Binding(
        key_field="order_id",
        params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys)}),
    )
    ```

    示例(带元信息):
    ```python
    Binding(
        key_field="order_id",
        params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys)}),
        meta=BindingFieldMeta(field_name="order_id", field_type=int),
    )
    ```
    """

    key_field: NormalizedLookupKeySpec
    """
    绑定的键字段名 (主键或外键)
    """

    params_builder: LoaderParamsBuilder
    """
    参数构建器类型:`(context) -> (args, kwargs)`
    """

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

    def build_params(self, context: "LoaderCallContextIr") -> LoaderCallParams:
        """构建调用参数"""
        return self.params_builder(context)


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

    callable: LoaderResultMapCallable
    """
    实际的用户注册的加载函数
    """

    extractor: Optional[LoaderExtractor] = None
    """
    数据提取器类型:`(key, loader_result) -> extracted_data`
    """

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


__all__ = [
    "BindingIr",
    "LoaderCallContextIr",
    "LoaderIr",
    "build_stable_lookup_key_list",
]
