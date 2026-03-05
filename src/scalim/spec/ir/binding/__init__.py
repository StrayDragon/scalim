from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Dict, Hashable, List, Mapping, Optional, Set, Tuple, Union, cast

from ....typedefs import RowData


def _stable_lookup_key_sort_key(value: Any) -> Any:
    if isinstance(value, tuple):
        items = cast("Tuple[Any, ...]", value)
        return ("tuple", tuple(_stable_lookup_key_sort_key(item) for item in items))
    return (type(value).__name__, repr(value))


def build_stable_lookup_key_list(lookup_keys: Set[Hashable]) -> List[Hashable]:
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

    batch_row_nth: List[Hashable] = field(default_factory=list)
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

    lookup_keys: Optional[Set[Hashable]] = None
    """
    引用加载器的查找键集合(已去重)
    """

    lookup_keys_list: Optional[List[Hashable]] = None
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

    key_field: Union[str, Tuple[str, ...]]
    """
    绑定的键字段名 (主键或外键)
    """

    params_builder: Callable[["LoaderCallContextIr"], Tuple[Tuple[Any, ...], Dict[str, Any]]]
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

    def build_params(self, context: "LoaderCallContextIr") -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        """构建调用参数"""
        return self.params_builder(context)


def _empty_bindings() -> "Mapping[Union[str, Tuple[str, ...]], BindingIr]":
    return MappingProxyType({})


@dataclass(frozen=True)
class LoaderIr:
    """
    [数据源]加载器(IR): 定义如何调用数据加载函数以及如何提取返回的数据
    """

    callable: Callable[..., Dict[Any, Any]]
    """
    实际的用户注册的加载函数
    """

    extractor: Optional[Callable[[Any, Any], Dict[Hashable, Any]]] = None
    """
    数据提取器类型:`(key, loader_result) -> extracted_data`
    """

    bindings: Mapping[Union[str, Tuple[str, ...]], BindingIr] = field(default_factory=_empty_bindings)
    """
    参数绑定映射(`key_field` -> `Binding`).使用 `Mapping` 确保不可变性.
    """

    def __post_init__(self) -> None:
        if isinstance(self.bindings, dict):
            object.__setattr__(self, "bindings", MappingProxyType(self.bindings))

    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        bindings = state.get("bindings")
        if isinstance(bindings, MappingProxyType):
            state["bindings"] = dict(bindings)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)
        bindings = getattr(self, "bindings", None)
        if isinstance(bindings, dict):
            typed_bindings = cast("Dict[Any, Any]", bindings)
            object.__setattr__(self, "bindings", MappingProxyType(typed_bindings))

    def get_binding(self, key_field: Union[str, Tuple[str, ...]]) -> Optional[BindingIr]:
        return self.bindings.get(key_field)


__all__ = [
    "BindingIr",
    "LoaderCallContextIr",
    "LoaderIr",
    "build_stable_lookup_key_list",
]
