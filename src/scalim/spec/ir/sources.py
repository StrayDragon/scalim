from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ...typedefs import SourceSpecIrCacheMode
from ...vendor.compact.typing_extensionsx import override
from .aliases import MainSourceLoaderCallable
from .binding import BindingIr, LoaderIr

if TYPE_CHECKING:
    from .relations import FieldRefIr


@dataclass(frozen=True)
class KeyIr:
    """
    Key(IR): 描述数据源返回映射的 key 结构
    """

    key: str | tuple[str, ...]
    """
    key 定义
    """

    cast: Callable[[Any], Hashable | None] | None = None
    """
    key 归一化转换: 用于 lookup key 类型对齐
    例如: cast=int 将 str("123") 转换为 int(123)
    """

    def __post_init__(self) -> None:
        if isinstance(self.key, str):
            key = self.key.strip()
            if key.startswith("(") and key.endswith(")") and "," in key:
                msg = f"Composite key must be tuple, got string: {self.key}"
                raise ValueError(msg)

    @override
    def __str__(self) -> str:
        return str(self.key)

    @override
    def __hash__(self) -> int:
        return hash(self.key)


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
    key 信息
    """

    loader_spec: LoaderIr
    """
    加载器信息
    """

    fk_fields: frozenset[str] = field(default_factory=frozenset)
    """
    外键字段名集合
    """

    cache_mode: SourceSpecIrCacheMode = SourceSpecIrCacheMode.NONE
    """
    缓存模式
    """

    lookup_chunk_size: int | None = None
    """
    keys 模式 LoadRef 的 lookup_keys 分片大小; None/0 表示不分片
    """

    bindings: dict[str | tuple[str, ...], BindingIr] = field(default_factory=dict, compare=False, hash=False)
    """
    参数绑定映射 (key_field -> Binding)
    """

    bind: BindingIr | None = None
    """
    默认绑定 (无 key_field 匹配时使用)
    """

    def get_binding(self, key_field: str | tuple[str, ...]) -> BindingIr | None:
        """获取指定键字段的绑定.

        Args:
            key_field: 键字段名(字符串或字符串元组,用于复合主键)
        """
        binding = self.loader_spec.get_binding(key_field)
        if binding is None:
            return self.bind
        return binding

    def is_preload_forever(self) -> bool:
        return self.cache_mode == SourceSpecIrCacheMode.PRELOAD_FOREVER

    def __getitem__(self, field_name: str) -> "FieldRefIr":
        """支持 Source["field"] 语法创建字段引用.

        Args:
            field_name: 字段名

        Example:
            orders_source["customer_id"].join(customers_source["customer_id"])

        Note:
            使用字符串类型注解避免前向引用问题
        """
        from .relations import FieldRefIr  # noqa: PLC0415

        return FieldRefIr(source=self, field_name=field_name)

    @override
    def __hash__(self) -> int:
        return hash(self.source_id)


@dataclass(frozen=True)
class MainSourceIr:
    """
    主数据源(IR): 以行流方式提供数据,由框架分配 row_id 进行索引
    """

    source_id: str
    """
    数据源唯一标识
    """

    loader: MainSourceLoaderCallable
    """
    主数据源加载器 (返回 Iterable[RowData])
    """

    params: dict[str, Any] = field(default_factory=dict)
    """
    Loader 静态参数 (直接透传给 loader)
    """

    order_by: tuple["OrderByKeyIr", ...] = field(default_factory=tuple)
    """
    批次内排序键(字段 + 方向).仅影响写入顺序,不改变 row_id 分配
    """

    row_id_key: str = "row_id"
    """
    内部行标识字段名 (框架维护)
    """

    def __getitem__(self, field_name: str) -> "FieldRefIr":
        """支持 MainSource["field"] 语法创建字段引用."""
        from .relations import FieldRefIr  # noqa: PLC0415

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
    排序字段 key (主数据源字段)
    """

    direction: str = "asc"
    """
    排序方向: asc/desc
    """


SourceRefIr = SourceIr | MainSourceIr
