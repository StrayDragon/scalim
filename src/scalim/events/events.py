# region imports

from dataclasses import dataclass
from typing import Any, Dict, Hashable, List, Optional

from ..typedefs import RelationLookupResult

# endregion


@dataclass(frozen=True)
class PipelineStartEvent:
    """管线开始事件.

    当管线开始执行时触发.
    """

    targets: List[str]
    """目标字段键列表."""

    batch_size: Optional[int]
    """配置的批处理大小(`None` 表示不分批)."""


@dataclass(frozen=True)
class PipelineEndEvent:
    """管线结束事件.

    当管线完成执行时触发.
    """

    total_batches: int
    """处理的批处理总数."""

    total_duration: float
    """总执行时间(秒)."""


@dataclass(frozen=True)
class BatchStartEvent:
    """批处理开始事件.

    当批处理开始处理时触发.
    """

    batch_num: int
    """批处理编号(从 1 开始)."""

    row_ids: List[Any]
    """此批次中的行标识列表."""


@dataclass(frozen=True)
class BatchEndEvent:
    """批处理结束事件.

    当批处理完成处理时触发.
    """

    batch_num: int
    """批处理编号(从 1 开始)."""

    duration: float
    """批处理耗时(秒)."""


@dataclass(frozen=True)
class LoaderCallEvent:
    """数据加载器调用事件.

    当数据加载器被调用时触发.
    """

    loader_name: str
    """加载器名称."""

    params: Dict[str, Any]
    """传递给加载器的参数."""

    result: Any
    """加载器返回的结果或摘要/样本."""

    duration: float
    """加载器执行耗时(秒)."""

    batch_num: Optional[int] = None
    """批次编号(可选)."""

    cache_status: Optional[str] = None
    """缓存命中状态(`hit`/`miss`,可选)."""

    cache_scope: Optional[str] = None
    """缓存作用域(例如 `batch`,可选)."""

    lookup_key_count: Optional[int] = None
    """本次调用的查找键数量(可选)."""

    field_keys: Optional[List[str]] = None
    """加载器关联字段键列表(可选)."""


@dataclass(frozen=True)
class LoaderRetryEvent:
    """加载重试事件.

    当一次加载调用失败且框架决定重试时触发(在进入等待休眠之前).
    """

    loader_name: str
    """加载器名称."""

    callsite: str
    """调用点标识(用于定位触发位置)."""

    attempt_num: int
    """当前重试次数(从 1 开始)."""

    max_attempts: int
    """最大尝试次数上限."""

    elapsed_seconds: float
    """已消耗的累计时间(秒,包含等待)."""

    sleep_seconds: float
    """本次重试前的等待时间(秒)."""

    error_type: str
    """异常类型名称."""

    error_message: Optional[str] = None
    """异常信息(可选)."""

    batch_num: Optional[int] = None
    """批次编号(可选)."""


@dataclass(frozen=True)
class FieldComputeEvent:
    """字段计算事件.

    当派生字段被计算时触发.
    """

    field_key: str
    """字段键."""

    row_id: Optional[Hashable]
    """行标识."""

    dependencies: Dict[str, Any]
    """依赖字段值映射."""

    result: Any
    """计算结果."""


@dataclass(frozen=True)
class ErrorEvent:
    """错误事件.

    当执行过程中发生错误时触发.
    """

    error: Exception
    """发生的异常对象."""

    context: Dict[str, Any]
    """额外的上下文信息."""


@dataclass(frozen=True)
class DiagnosticWarningEvent:
    """诊断告警事件.

    用于记录非阻断性问题,提示用户检查数据或配置.
    """

    message: str
    """可读的告警说明."""

    source_id: Optional[str]
    """关联的目标数据源标识."""

    field_id: Optional[str]
    """当前计算字段标识."""

    lookup_key: Any
    """外键值/关联键."""

    row_id: Optional[Hashable]
    """行标识(可选)."""


@dataclass(frozen=True)
class FieldSlimEvent:
    """字段瘦身事件(FR022)."""

    field_key: str
    """字段键."""

    reason: str
    """触发原因标识."""

    batch_num: Optional[int]
    """批次编号(可选)."""

    remaining_fields: Optional[int]
    """瘦身后保留的字段数量."""


@dataclass(frozen=True)
class RowWriteEvent:
    """行写入事件(FR023)."""

    row_id: Hashable
    """行标识."""

    field_count: int
    """写入的字段数量."""

    batch_num: Optional[int]
    """批次编号(可选)."""

    row_index: Optional[int]
    """批次内行序号(从 0 开始)."""


@dataclass(frozen=True)
class RowReleaseEvent:
    """行内存释放事件(FR023)."""

    row_id: Hashable
    """行标识."""

    released_fields: List[str]
    """已释放的字段键列表."""

    retained_fields: List[str]
    """仍保留的字段键列表."""

    batch_num: Optional[int]
    """批次编号(可选)."""


@dataclass(frozen=True)
class LoaderSlimEvent:
    """加载器结果瘦身事件(FR022)."""

    loader_name: str
    """加载器名称."""

    original_keys: int
    """瘦身前的键数量."""

    extracted_fields: List[str]
    """被抽取/保留的字段键列表."""

    batch_num: Optional[int]
    """批次编号(可选)."""


@dataclass(frozen=True)
class ColumnWriteEvent:
    """列写入事件(FR023)."""

    field_key: str
    """字段键."""

    row_count: int
    """写入的行数."""

    batch_num: int
    """批次编号."""


@dataclass(frozen=True)
class RelationLookupEvent:
    """关联查找事件."""

    field_key: str
    """当前字段键."""

    row_id: Hashable
    """行标识."""

    fk_raw: Any
    """原始外键值."""

    fk_normalized: Any
    """归一化后的外键值."""

    target_source: str
    """目标数据源标识."""

    result: RelationLookupResult
    """关联查找结果类型."""

    fk_type: Optional[str] = None
    """原始外键类型名称(可选)."""

    expected_type: Optional[str] = None
    """期望的外键类型名称(可选)."""

    error_message: Optional[str] = None
    """错误说明(可选)."""


@dataclass(frozen=True)
class StageSpanEvent:
    """阶段耗时事件(`loader`/`compute`/`write`)."""

    stage: str
    """阶段名称(例如 `loader`/`compute`/`write`)."""

    batch_num: int
    """批次编号."""

    duration: float
    """阶段耗时(秒)."""


@dataclass(frozen=True)
class AdaptiveSchedulerDecisionEvent:
    """自适应调度器决策事件.

    仅在 `parallel_mode=\"adaptive\"` 且已订阅此事件时触发(按需启用).
    """

    batch_num: int
    """批次编号."""

    layer_index: int
    """当前调度层序号(从 0 开始)."""

    decision: str
    """决策结果标识."""

    backend: str
    """执行后端标识."""

    reason: Optional[str] = None
    """决策原因说明(可选)."""

    layer_task_count: Optional[int] = None
    """当前层任务数量(可选)."""

    process_failure_mode: Optional[str] = None
    """进程后端失败处理模式(可选)."""

    pool_limits: Optional[Dict[str, int]] = None
    """执行器池容量限制映射(可选)."""

    pool_wait_ms_total: Optional[Dict[str, float]] = None
    """按池统计的等待总时长(毫秒,可选)."""

    pool_wait_ms_max: Optional[Dict[str, float]] = None
    """按池统计的单次等待最大时长(毫秒,可选)."""

    pool_wait_count: Optional[Dict[str, int]] = None
    """按池统计的等待次数(可选)."""


__all__ = [
    "AdaptiveSchedulerDecisionEvent",
    "BatchEndEvent",
    "BatchStartEvent",
    "ColumnWriteEvent",
    "DiagnosticWarningEvent",
    "ErrorEvent",
    "FieldComputeEvent",
    "FieldSlimEvent",
    "LoaderCallEvent",
    "LoaderRetryEvent",
    "LoaderSlimEvent",
    "PipelineEndEvent",
    "PipelineStartEvent",
    "RelationLookupEvent",
    "RowReleaseEvent",
    "RowWriteEvent",
    "StageSpanEvent",
]
