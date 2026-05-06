# region imports

from decimal import Decimal
from typing import Dict, Hashable, List, Mapping, Sequence, Set, Tuple, Union

from ._internal.utils.policy import ensure_policy_enum, parse_policy_value
from .vendor.compact import StrEnum
from .vendor.compact.typing_extensionsx import Literal

# endregion

FieldValue = Union[int, float, Decimal, str, bool, None]
"""字段值的常见具体类型"""

RowData = Mapping[str, FieldValue]
"""行数据类型 - 从字段键到字段值的映射"""

RuntimeValue = object
"""运行时动态值边界: 外部输入先按 `object` 处理,再做显式窄化."""

StaticParams = Dict[str, RuntimeValue]
"""静态参数映射: 用于主源/加载器的透传参数."""

# region literal types
ParallelMode = Literal["seq", "adaptive"]
"""执行并行模式

- `seq`: 纯串行执行(可预测、易调试)
- `adaptive`: 自动调度批次内 `LoadRef(keys)` 的并发 `fan-out`/`fan-in`,并在提交点稳定归并与回放事件
"""

KeyNormalizationMode = Literal["raw", "auto_str", "force_str"]
"""`key` 规范化模式

- `raw`: 保持原始 `key` 口径(默认)
- `auto_str`: 仅在未显式配置 `cast` 时,按稳定字符串口径匹配(缺省回退)
- `force_str`: 强制按稳定字符串口径匹配(即使显式 `cast` 也在最终匹配边界做字符串规范化)
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
# - `RecordIndex`: 批次内的记录索引 (0, 1, 2, ...)
# - `BusinessKey`: 业务层面的记录标识 (`str` 或复合键 `Tuple[str, ...]`)
# - `RecordKey`: 通用记录键 (可以是索引或业务键)
#
# 命名说明:
# - 使用 `Record` 而非 `Row` 以支持未来的流式输出场景 (`JSON Lines`, 事件流等)
# - 但为了向后兼容, 保留 `RowId`/`RowIdSeq`/`RowIdList` 作为 `BusinessKey` 的别名

RecordIndex = int
"""批次内的记录索引 (0, 1, 2, ...), 由框架内部分配."""

BusinessKey = Union[str, Tuple[str, ...]]
"""业务层面的记录标识, 来自 `loader` 返回的 `Dict` 的 `key`. 可以是 `str` 或复合键 `Tuple[str, ...]`."""

RecordKey = Union[RecordIndex, BusinessKey]
"""通用记录键 - 可以是批次内索引 (`int`) 或业务 `key` (`str`/`Tuple[str, ...]`)."""

RecordKeySeq = Sequence[RecordKey]
"""记录键序列, 用于函数参数 (只读, 协变)."""

# 向后兼容别名 (推荐使用新名称)
RowId = BusinessKey
"""[兼容别名] 单个行标识, 等同于 BusinessKey."""

RowIdSeq = Sequence[RowId]
"""[兼容别名] 行标识序列, 用于函数参数 (只读, 接受 `List`/`Tuple`)."""

RowIdList = List[RowId]
"""[兼容别名] 行标识列表, 用于内部存储和返回值 (可变)."""

LoaderResult = Dict[RowId, RowData]
"""`Loader` 函数返回的数据映射: `row_id` -> `row_data`."""

LookupKey = Hashable
"""关联查找键: 单键与复合键统一按可哈希值处理."""

LookupKeySeq = Sequence[LookupKey]
"""关联查找键序列 (只读)."""

LookupKeyList = List[LookupKey]
"""关联查找键列表."""

LookupKeySet = Set[LookupKey]
"""关联查找键集合."""

LoaderResultValue = RuntimeValue
"""`Loader` 返回映射中的单个结果值."""

LoaderResultMapping = Mapping[LookupKey, LoaderResultValue]
"""`Loader` 结果的只读映射视图."""

LoaderResultMap = Dict[LookupKey, LoaderResultValue]
"""`Loader` 结果的具体字典形态,用于缓存与合并."""

LoaderCallArgs = Tuple[RuntimeValue, ...]
"""调用 `Loader` 时的位置参数元组."""

LoaderCallKwargs = Dict[str, RuntimeValue]
"""调用 `Loader` 时的关键字参数映射."""

LoaderCallParams = Tuple[LoaderCallArgs, LoaderCallKwargs]
"""`params_builder` 构造出的 `(args, kwargs)` 结果."""

# `Sink` 接口使用的类型 (等同于 `RecordKey`/`RecordKeySeq`)
SinkRowKey = RecordKey
"""[`Sink` 接口] 记录键类型, 等同于 `RecordKey`."""

SinkRowKeySeq = RecordKeySeq
"""[`Sink` 接口] 记录键序列, 等同于 `RecordKeySeq`."""

# endregion

DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY = (
    "检测到关联键为 float,auto 模式将忽略该值.请配置 lookup_cast/value_cast 或调整 relation 定义以确保类型一致."
)
"""关联键为 `float` 的诊断告警文案"""


class FailurePolicy(StrEnum):
    """失败策略(封闭集合;用于 `workflow` 与多输出路由).

    - `ALL_FAIL`: 任一子任务失败即失败(默认)
    - `PRIMARY_ONLY`: 非主任务失败不阻断(记录并跳过/禁用)
    """

    ALL_FAIL = "all_fail"
    PRIMARY_ONLY = "primary_only"


FailurePolicyValue = str
"""失败策略的规范化内置 `str` 值(用于运行时存储与 `state`/`wire` 边界)."""

_DEFAULT_FAILURE_POLICY = FailurePolicy.ALL_FAIL


def parse_failure_policy(value: object, *, label: str = "failure_policy") -> FailurePolicyValue:
    """从配置/状态边界解析并校验 `failure_policy`(封闭集合;快速失败)."""
    return parse_policy_value(
        FailurePolicy,
        value,
        label=label,
        default=_DEFAULT_FAILURE_POLICY,
        normalize=lambda v: v.strip().lower().replace("-", "_"),
        allow_empty=True,
    )


def normalize_failure_policy(value: FailurePolicy, *, label: str = "failure_policy") -> FailurePolicyValue:
    """公开 `API`: 严格只接受 `Enum`,并返回规范化后的内置 `str` 值."""
    policy = ensure_policy_enum(FailurePolicy, value, label=label)
    return str(policy.value)


class SourceSpecIrCacheMode(StrEnum):
    """数据源缓存模式枚举.

    用于 `SourceDef.cache_mode` 属性,避免字符串字面量满天飞.

    属性:
        `NONE`: 默认模式,不缓存
        `PRELOAD_FOREVER`: 预加载后永久有效,不参与内存优化剪枝
    """

    NONE = "none"
    """默认模式:不缓存;每次访问都调用加载器函数."""

    PRELOAD_FOREVER = "preload_forever"
    """预加载永久缓存:在流水线开始前预加载全部数据,之后永久有效."""

    def is_caching(self) -> bool:
        """是否启用缓存模式"""
        return self != SourceSpecIrCacheMode.NONE


__all__ = ()
