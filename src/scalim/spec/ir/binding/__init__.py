from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, cast

from ....typedefs import RowData


def _stable_lookup_key_sort_key(value: Any) -> Any:
    if isinstance(value, tuple):
        items = cast("tuple[Any, ...]", value)
        return ("tuple", tuple(_stable_lookup_key_sort_key(item) for item in items))
    return (type(value).__name__, repr(value))


def stable_lookup_keys_list(lookup_keys: set[Hashable]) -> list[Hashable]:
    """稳定序列化 lookup keys 为 list.

    用途:
    - `use_keys.as=list` 需要 list 容器形态;
    - lookup keys 在执行路径中常以 set 去重,其迭代顺序受 `PYTHONHASHSEED` 影响;
    - 本函数提供确定性的输出顺序,提升回归可重复性与外部缓存命中可预测性.
    """

    return sorted(lookup_keys, key=_stable_lookup_key_sort_key)


@dataclass(frozen=True)
class LoaderCallContextIr:
    """
    加载器调用上下文(IR): 框架在调用 loader 前构建此对象,传递给用户的 params_builder 回调函数
    """

    batch_row_nth: list[Hashable] = field(default_factory=list)
    """
    当前批次的行号列表 (主源流的行索引)
    """

    source_id: str = ""
    """
    关联的数据源ID
    """

    field_keys: list[str] = field(default_factory=list)
    """
    需要从此 loader 加载的字段列表
    """

    is_ref_loader: bool = False
    """
    是否是 ref loader (外键关联加载)
    """

    lookup_keys: set[Hashable] | None = None
    """
    Ref loader 的 lookup key 集合 (已去重)
    """

    lookup_keys_list: list[Hashable] | None = None
    """
    Ref loader 的 lookup key 列表 (由 lookup_keys 生成)
    """

    batch_rows: list[RowData] | None = None
    """
    rows 模式下的当前批次行上下文 (主源 + 已 join)
    """


@dataclass(frozen=True)
class BindingIr:
    """参数绑定(IR): 定义如何根据运行时上下文构建 loader 调用参数.

    params_builder: 返回调用参数, 返回 (args, kwargs) 元组
       lambda ctx: ((), {"order_ids": ctx.lookup_keys})

    Example:
        Binding(
            key_field="order_id",
            params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys)})
        )

    Example (带元信息):
        Binding(
            key_field="order_id",
            params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys)}),
            meta=BindingFieldMeta(field_name="order_id", field_type=int)
        )
    """

    key_field: str | tuple[str, ...]
    """
    绑定的键字段名 (主键或外键)
    """

    params_builder: Callable[["LoaderCallContextIr"], tuple[tuple[Any, ...], dict[str, Any]]]
    """
    参数构建器类型: (context) -> (args, kwargs)
    """

    mode: str = "keys"
    """
    绑定模式: keys 或 rows
    """

    as_: str = "set"
    """
    keys 模式下的容器形态: set 或 list
    """

    cache_mode: str = "none"
    """
    rows 模式缓存策略: none 或 batch. (YAML/DSL 未配置时 rows 默认 batch)
    """

    param_name: str | None = None
    """
    params_builder 绑定的参数名(可选,用于诊断与签名稳定性)
    """

    def build_params(self, context: "LoaderCallContextIr") -> tuple[tuple[Any, ...], dict[str, Any]]:
        """构建调用参数"""
        return self.params_builder(context)


def _empty_bindings() -> "Mapping[str | tuple[str, ...], BindingIr]":
    return MappingProxyType({})


@dataclass(frozen=True)
class LoaderIr:
    """
    [数据源]加载器(IR): 定义如何调用数据加载函数以及如何提取返回的数据
    """

    callable: Callable[..., dict[Any, Any]]
    """
    实际的用户注册的加载函数
    """

    extractor: Callable[[Any, Any], dict[Hashable, Any]] | None = None
    """
    数据提取器类型: (key, loader_result) -> extracted_data
    """

    bindings: Mapping[str | tuple[str, ...], BindingIr] = field(default_factory=_empty_bindings)
    """
    参数绑定映射 (key_field -> Binding). 使用 Mapping 确保不可变性.
    """

    def __post_init__(self) -> None:
        if isinstance(self.bindings, dict):
            object.__setattr__(self, "bindings", MappingProxyType(self.bindings))

    def __getstate__(self) -> dict[str, Any]:
        state = dict(self.__dict__)
        bindings = state.get("bindings")
        if isinstance(bindings, MappingProxyType):
            state["bindings"] = dict(bindings)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)
        bindings = getattr(self, "bindings", None)
        if isinstance(bindings, dict):
            typed_bindings = cast("dict[Any, Any]", bindings)
            object.__setattr__(self, "bindings", MappingProxyType(typed_bindings))

    def get_binding(self, key_field: str | tuple[str, ...]) -> BindingIr | None:
        return self.bindings.get(key_field)
