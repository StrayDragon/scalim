from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Sequence, Tuple, Union, cast

from ...typedefs import LoaderResultMap, LoaderResultMapping, SourceSpecIrCacheMode, StaticParams
from ...vendor.compact.typing_extensionsx import override
from .aliases import LookupKeyCast, MainSourceRowIterableCallable, NormalizedLookupKeySpec
from .binding import BindingIr, LoaderIr
from .relations import FieldRefIr


@dataclass(frozen=True)
class KeyIr:
    """
    `Key`(IR): 描述数据源返回映射的键结构
    """

    key: Union[str, Tuple[str, ...]]
    """
    键定义.
    """

    cast: Optional[LookupKeyCast] = None
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

    kind: str
    """`normalize` 预置类型."""

    key_field: str
    """用于建立索引的 `row` 字段名."""

    on_conflict: str = "error"
    """`duplicate key` 冲突策略(`error`/`first`/`last`)."""

    def apply(self, result: object, *, source_id: str) -> LoaderResultMapping:
        if self.kind == "index_by_key":
            return _normalize_index_by_key(
                result,
                source_id=source_id,
                key_field=self.key_field,
                on_conflict=self.on_conflict,
            )
        msg = "Unknown normalize.kind '{}' for source '{}'".format(self.kind, source_id)
        raise ValueError(msg)


def _normalize_index_by_key(
    result: object,
    *,
    source_id: str,
    key_field: str,
    on_conflict: str,
) -> LoaderResultMapping:
    # 若 `loader` 已返回 `mapping`,则直接透传.
    if isinstance(result, Mapping):
        return cast("LoaderResultMapping", result)

    if not isinstance(result, (list, tuple)):
        msg = "Source '{}' normalize.index_by_key expected loader result list[row], got '{}'".format(source_id, type(result).__name__)
        raise TypeError(msg)

    indexed: LoaderResultMap = {}
    for idx, item in enumerate(cast("Sequence[object]", result)):
        row = _normalize_index_by_key_require_row(item, source_id=source_id, idx=idx)
        key = _normalize_index_by_key_extract_key(row, source_id=source_id, key_field=key_field, idx=idx)
        _normalize_index_by_key_insert(indexed, key=key, row=row, source_id=source_id, on_conflict=on_conflict)

    return indexed


def _normalize_index_by_key_require_row(item: object, *, source_id: str, idx: int) -> "Mapping[str, object]":
    if not isinstance(item, Mapping):
        msg = "Source '{}' normalize.index_by_key expected list[row] where row is a Mapping, got '{}' at index {}".format(
            source_id,
            type(item).__name__,
            idx,
        )
        raise TypeError(msg)
    return cast("Mapping[str, object]", item)


def _normalize_index_by_key_extract_key(
    row: "Mapping[str, object]",
    *,
    source_id: str,
    key_field: str,
    idx: int,
) -> Hashable:
    if key_field not in row:
        msg = "Source '{}' normalize.index_by_key missing key_field '{}' at index {}".format(source_id, key_field, idx)
        raise KeyError(msg)
    key = row.get(key_field)
    if key is None:
        msg = "Source '{}' normalize.index_by_key key_field '{}' is None at index {}".format(source_id, key_field, idx)
        raise ValueError(msg)
    if not isinstance(key, Hashable):
        msg = "Source '{}' normalize.index_by_key key_field '{}' must be hashable, got '{}' at index {}".format(
            source_id,
            key_field,
            type(key).__name__,
            idx,
        )
        raise TypeError(msg)
    return key


def _normalize_index_by_key_insert(
    indexed: LoaderResultMap,
    *,
    key: Hashable,
    row: "Mapping[str, object]",
    source_id: str,
    on_conflict: str,
) -> None:
    if key not in indexed:
        indexed[key] = row
        return
    if on_conflict == "first":
        return
    if on_conflict == "last":
        indexed[key] = row
        return
    if on_conflict != "error":
        msg = "Source '{}' normalize.index_by_key has invalid on_conflict '{}'".format(source_id, on_conflict)
        raise ValueError(msg)
    msg = "Source '{}' normalize.index_by_key duplicate key '{}'".format(source_id, key)
    raise ValueError(msg)


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

    bindings: Dict[NormalizedLookupKeySpec, BindingIr] = field(default_factory=dict, compare=False, hash=False)
    """
    参数绑定映射(`key_field` -> `BindingIr`).
    """

    bind: Optional[BindingIr] = None
    """
    默认绑定(当无 `key_field` 匹配时使用).
    """

    normalize: Optional[SourceNormalizeIr] = None
    """
    数据源 `whole-result` `normalize` 配置(可选).
    """

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

    loader: MainSourceRowIterableCallable
    """
    主数据源加载器(返回 `Iterable[RowData]`).
    """

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
