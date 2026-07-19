from types import MappingProxyType
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple, Union

from ...typedefs import LoaderResultMapping, RuntimeValue, SourceSpecIrCacheMode, StaticParams
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass, field
from ._relations import FieldRefIr
from ._source_normalize import (
    NormalizeKind,
    NormalizeOnConflict,
    NormalizeOnEmpty,
    NormalizeOnMissing,
    NormalizeOnNone,
    SourceNormalizeProjectFieldRuleIr,
    SourceNormalizeStepIr,
    normalize_call_by,
    normalize_index_by_key,
    normalize_map_values,
    normalize_project_fields,
    normalize_take_first,
)
from .aliases import NormalizedLookupKeySpec
from .binding import BindingIr, LoaderIr
from .callable_refs import CallableRefIr
from .lookup_casts import LookupCastSpecIr


def _default_bindings() -> Dict[NormalizedLookupKeySpec, BindingIr]:
    return {}


@dataclass(frozen=True)
class KeyIr:
    """
    `Key`(IR): 描述数据源返回映射的键结构
    """

    key: Union[str, Tuple[str, ...]]
    """
    键定义.
    """

    cast: Optional[LookupCastSpecIr] = None
    """
    键归一化转换:用于对齐关联键类型.

    例如:`cast=int` 会将 `str(\"123\")` 转换为 `int(123)`.
    """

    def __post_init__(self) -> None:
        if isinstance(self.key, str):
            key = self.key.strip()
            if key.startswith("(") and key.endswith(")") and "," in key:
                msg = "Composite key must be tuple, got string: {}".format(self.key)
                raise ValueError(msg)

    @override
    def __str__(self) -> str:
        return str(self.key)

    @override
    def __hash__(self) -> int:
        return hash(self.key)


@dataclass(frozen=True)
class SourceNormalizeIr:
    """数据源 `whole-result` `normalize` 配置(`IR`)."""

    kind: NormalizeKind
    """`normalize` 预置类型."""

    key_field: str = ""
    """用于建立索引的 `row` 字段名."""

    on_conflict: NormalizeOnConflict = "error"
    """`duplicate key` 冲突策略(`error`/`first`/`last`)."""

    on_none: NormalizeOnNone = "raise"
    """`key_field is None` 策略(`raise`/`skip`;仅 `index_by_key`)."""

    on_empty: NormalizeOnEmpty = "miss"
    """空列表策略(`miss`/`null`/`error`)."""

    on_missing: NormalizeOnMissing = "error"
    """缺失路径策略(`error`/`null`)."""

    fields: Tuple[SourceNormalizeProjectFieldRuleIr, ...] = ()
    """`project_fields` 的投影规则(按顺序)."""

    steps: Tuple[SourceNormalizeStepIr, ...] = ()
    """用于 `normalize.map_values` 分支的归一化步骤(按顺序)."""

    call_by_ref: Optional[CallableRefIr] = None
    """可选: `normalize.call_by` 可调用引用描述(纯数据,不包含可调用对象)."""

    def apply(
        self,
        result: RuntimeValue,
        *,
        source_id: str,
        call_by: Optional[Any] = None,
    ) -> LoaderResultMapping:
        normalized: LoaderResultMapping
        if self.kind == "index_by_key":
            normalized = normalize_index_by_key(
                result,
                source_id=source_id,
                key_field=self.key_field,
                on_conflict=self.on_conflict,
                on_none=self.on_none,
            )
        elif self.kind == "take_first":
            normalized = normalize_take_first(
                result,
                source_id=source_id,
                on_empty=self.on_empty,
            )
        elif self.kind == "project_fields":
            normalized = normalize_project_fields(
                result,
                source_id=source_id,
                fields=self.fields,
                on_missing=self.on_missing,
            )
        elif self.kind == "map_values":
            normalized = normalize_map_values(
                result,
                source_id=source_id,
                steps=self.steps,
            )
        else:
            msg = "Unknown normalize.kind '{}' for source '{}'".format(self.kind, source_id)
            raise ValueError(msg)

        if self.call_by_ref is None:
            return normalized
        if call_by is None:
            msg = "Source '{}' normalize.call_by_ref requires runtime resolution before apply()".format(source_id)
            raise ValueError(msg)
        if not callable(call_by):
            msg = "Source '{}' normalize.call_by_ref expects callable runtime binding, got '{}'".format(source_id, type(call_by).__name__)
            raise TypeError(msg)
        return normalize_call_by(
            normalized,
            source_id=source_id,
            kind=self.kind,
            call_by=call_by,
        )


@dataclass(frozen=True)
class SourceIr:
    """
    数据源(IR): 定义一个数据源的完整信息,包括主键、外键、加载器和绑定
    """

    source_id: str
    """
    数据源唯一标识
    """

    key: KeyIr
    """
    键信息.
    """

    loader_spec: LoaderIr
    """
    加载器信息
    """

    fk_fields: FrozenSet[str] = field(default_factory=frozenset)
    """
    外键字段名集合
    """

    cache_mode: SourceSpecIrCacheMode = SourceSpecIrCacheMode.NONE
    """
    缓存模式
    """

    lookup_chunk_size: Optional[int] = None
    """
    在 `keys` 模式下,引用加载的 `lookup_keys` 分片大小;`None`/`0` 表示不分片.
    """

    bindings: Mapping[NormalizedLookupKeySpec, BindingIr] = field(default_factory=_default_bindings, compare=False, hash=False)
    """
    参数绑定映射(`key_field` -> `BindingIr`).
    运行时为 `MappingProxyType` — 浅不可变.
    """

    bind: Optional[BindingIr] = None
    """
    默认绑定(当无 `key_field` 匹配时使用).
    """

    normalize: Optional[SourceNormalizeIr] = None
    """
    数据源 `whole-result` `normalize` 配置(可选).
    """

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", MappingProxyType(dict(self.bindings)))

    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        bindings = state.get("bindings")
        if isinstance(bindings, MappingProxyType):
            state["bindings"] = dict(bindings)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)
        self.__post_init__()

    def get_binding(self, key_field: NormalizedLookupKeySpec) -> Optional[BindingIr]:
        """获取指定键字段的绑定.

        参数:
            `key_field`: 键字段名(字符串或字符串元组,用于复合主键)
        """
        binding = self.loader_spec.get_binding(key_field)
        if binding is None:
            return self.bind
        return binding

    def is_preload_forever(self) -> bool:
        return self.cache_mode == SourceSpecIrCacheMode.PRELOAD_FOREVER

    def __getitem__(self, field_name: str) -> FieldRefIr:
        """支持 `Source[\"field\"]` 语法创建字段引用.

        参数:
            `field_name`: 字段名

        示例:
            - `orders_source[\"customer_id\"].join(customers_source[\"customer_id\"])`

        """
        return FieldRefIr(source=self, field_name=field_name)

    @override
    def __hash__(self) -> int:
        return hash(self.source_id)


@dataclass(frozen=True)
class MainSourceIr:
    """
    主数据源(IR): 以行流方式提供数据,由框架分配 `row_id` 进行索引
    """

    source_id: str
    """
    数据源唯一标识
    """

    loader_ref: CallableRefIr
    """主数据源加载器引用描述(纯数据,不包含可调用对象)."""

    params: StaticParams = field(default_factory=dict)
    """
    加载器静态参数(直接透传给加载器函数).
    """

    order_by: Tuple["OrderByKeyIr", ...] = field(default_factory=tuple)
    """
    批次内排序键(字段 + 方向);仅影响写入顺序,不改变 `row_id` 分配.
    """

    row_id_key: str = "row_id"
    """
    内部行标识字段名 (框架维护)
    """

    def __getitem__(self, field_name: str) -> FieldRefIr:
        """支持 `MainSource[\"field\"]` 语法创建字段引用."""
        return FieldRefIr(source=self, field_name=field_name)

    @override
    def __hash__(self) -> int:
        return hash(self.source_id)


@dataclass(frozen=True)
class OrderByKeyIr:
    """
    主数据源批次排序键(IR)
    """

    field_key: str
    """
    排序字段键(主数据源字段).
    """

    direction: str = "asc"
    """
    排序方向:`asc`/`desc`.
    """


SourceRefIr = Union["SourceIr", "MainSourceIr"]

__all__ = ()
