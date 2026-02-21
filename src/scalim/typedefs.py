# region imports

from collections.abc import Mapping, Sequence

from .vendor.compact import StrEnum
from .vendor.compact.typing_extensionsx import Literal

# endregion

FieldValue = int | float | str | bool | None
"""字段值的常见具体类型"""

RowData = Mapping[str, FieldValue]
"""行数据类型 - 从字段键到字段值的映射"""

# region literal types
ParallelMode = Literal["seq", "adaptive"]
"""执行并行模式

- seq: 纯串行执行(可预测、易调试)
- adaptive: 自动调度批次内 LoadRef(keys) 的并发 fan-out/fan-in,并在提交点稳定归并与回放事件
"""

PerformanceReportFormat = Literal["console", "json", "csv", "none"]
"""性能报告格式"""

RelationReportFormat = Literal["console", "json", "none"]
"""关联报告格式"""

RelationLookupResult = Literal["hit", "miss", "null_key", "type_error"]
"""关联查找结果类型"""

FieldPresentationKind = Literal["generic", "csv", "excel", "pandas"]
"""字段展示类型"""
# endregion

# region record key types
# 记录键类型体系:
# - RecordIndex: 批次内的记录索引 (0, 1, 2, ...)
# - BusinessKey: 业务层面的记录标识 (str 或复合键 Tuple[str, ...])
# - RecordKey: 通用记录键 (可以是索引或业务 key)
#
# 命名说明:
# - 使用 "Record" 而非 "Row" 以支持未来的流式输出场景 (JSON Lines, 事件流等)
# - 但为了向后兼容, 保留 RowId/RowIdSeq/RowIdList 作为 BusinessKey 的别名

RecordIndex = int
"""批次内的记录索引 (0, 1, 2, ...), 由框架内部分配."""

BusinessKey = str | tuple[str, ...]
"""业务层面的记录标识, 来自 loader 返回的 Dict 的 key. 可以是 str 或复合键 Tuple[str, ...]."""

RecordKey = RecordIndex | BusinessKey
"""通用记录键 - 可以是批次内索引 (int) 或业务 key (str/Tuple[str,...])."""

RecordKeySeq = Sequence[RecordKey]
"""记录键序列, 用于函数参数 (只读, 协变)."""

# 向后兼容别名 (推荐使用新名称)
RowId = BusinessKey
"""[兼容别名] 单个行标识, 等同于 BusinessKey."""

RowIdSeq = Sequence[RowId]
"""[兼容别名] 行标识序列, 用于函数参数 (只读, 接受 List/Tuple)."""

RowIdList = list[RowId]
"""[兼容别名] 行标识列表, 用于内部存储和返回值 (可变)."""

LoaderResult = dict[RowId, RowData]
"""Loader 函数返回的数据映射: row_id -> row_data."""

# Sink 接口使用的类型 (等同于 RecordKey/RecordKeySeq)
SinkRowKey = RecordKey
"""[Sink 接口] 记录键类型, 等同于 RecordKey."""

SinkRowKeySeq = RecordKeySeq
"""[Sink 接口] 记录键序列, 等同于 RecordKeySeq."""

# endregion

DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY = (
    "检测到关联键为 float,auto 模式将忽略该值.请配置 lookup_cast/value_cast 或调整 relation 定义以确保类型一致."
)
"""关联键为 float 的诊断告警文案"""


class SourceSpecIrCacheMode(StrEnum):
    """数据源缓存模式枚举.

    用于 SourceDef.cache_mode 属性,避免字符串字面量满天飞.

    Attributes:
        NONE: 默认模式,不缓存
        PRELOAD_FOREVER: 预加载后永久有效,不参与内存优化剪枝
    """

    NONE = "none"
    """默认模式 - 不缓存,每次访问都调用 loader"""

    PRELOAD_FOREVER = "preload_forever"
    """预加载永久缓存 - pipeline 开始前预加载全部数据,之后永久有效"""

    def is_caching(self) -> bool:
        """是否启用缓存模式"""
        return self != SourceSpecIrCacheMode.NONE
