# region imports

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any

from ..typedefs import RelationLookupResult

# endregion


@dataclass(frozen=True)
class PipelineStartEvent:
    """管道开始事件.

    当管道开始执行时触发.

    Attributes:
        targets: 目标字段键列表
        batch_size: 配置的批处理大小
    """

    targets: list[str]
    batch_size: int


@dataclass(frozen=True)
class PipelineEndEvent:
    """管道结束事件.

    当管道完成执行时触发.

    Attributes:
        total_batches: 处理的批处理总数
        total_duration: 总执行时间(秒)
    """

    total_batches: int
    total_duration: float


@dataclass(frozen=True)
class BatchStartEvent:
    """批处理开始事件.

    当批处理开始处理时触发.

    Attributes:
        batch_num: 批处理编号(从1开始)
        row_ids: 此批处理中行标识列表
    """

    batch_num: int
    row_ids: list[Any]


@dataclass(frozen=True)
class BatchEndEvent:
    """批处理结束事件.

    当批处理完成处理时触发.

    Attributes:
        batch_num: 批处理编号(从1开始)
        duration: 批处理时间(秒)
    """

    batch_num: int
    duration: float


@dataclass(frozen=True)
class LoaderCallEvent:
    """数据加载器调用事件.

    当数据加载器被调用时触发.

    Attributes:
        loader_name: 加载器名称
        params: 传递给加载器的参数
        result: 加载器返回的结果或摘要/样本
        duration: 加载器执行时间(秒)
        batch_num: 批次编号(可选)
        cache_status: 缓存命中状态(hit/miss,可选)
        cache_scope: 缓存作用域(例如 batch,可选)
        lookup_key_count: lookup_keys 数量(可选)
        field_keys: loader 关联字段列表(可选)
    """

    loader_name: str
    params: dict[str, Any]
    result: Any
    duration: float
    batch_num: int | None = None
    cache_status: str | None = None
    cache_scope: str | None = None
    lookup_key_count: int | None = None
    field_keys: list[str] | None = None


@dataclass(frozen=True)
class LoaderRetryEvent:
    """Loader retry attempt event.

    Emitted when a loader call fails and Scalim decides to retry (before sleeping).
    """

    loader_name: str
    callsite: str
    attempt_num: int
    max_attempts: int
    elapsed_seconds: float
    sleep_seconds: float
    error_type: str
    error_message: str | None = None
    batch_num: int | None = None


@dataclass(frozen=True)
class FieldComputeEvent:
    """字段计算事件.

    当派生字段被计算时触发.

    Attributes:
        field_key: 字段键
        row_id: 行标识
        dependencies: 依赖字段值
        result: 计算结果
    """

    field_key: str
    row_id: Hashable
    dependencies: dict[str, Any]
    result: Any


@dataclass(frozen=True)
class ErrorEvent:
    """错误事件.

    当执行过程中发生错误时触发.

    Attributes:
        error: 发生的异常
        context: 额外的上下文信息
    """

    error: Exception
    context: dict[str, Any]


@dataclass(frozen=True)
class DiagnosticWarningEvent:
    """诊断告警事件.

    用于记录非阻断性问题,提示用户检查数据或配置.

    Attributes:
        message: 可读告警说明
        source_id: 关联目标数据源
        field_id: 当前计算字段
        lookup_key: 外键值/关联键
        row_id: 行标识
    """

    message: str
    source_id: str
    field_id: str
    lookup_key: Any
    row_id: Hashable


@dataclass(frozen=True)
class FieldSlimEvent:
    """字段瘦身事件 (FR022)."""

    field_key: str
    reason: str
    batch_num: int
    remaining_fields: int


@dataclass(frozen=True)
class RowWriteEvent:
    """行写入事件 (FR023)."""

    row_id: Hashable
    field_count: int
    batch_num: int
    row_index: int


@dataclass(frozen=True)
class RowReleaseEvent:
    """行内存释放事件 (FR023)."""

    row_id: Hashable
    released_fields: list[str]
    retained_fields: list[str]
    batch_num: int


@dataclass(frozen=True)
class LoaderSlimEvent:
    """加载器结果瘦身事件 (FR022)."""

    loader_name: str
    original_keys: int
    extracted_fields: list[str]
    batch_num: int


@dataclass(frozen=True)
class ColumnWriteEvent:
    """列写入事件 (FR023)."""

    field_key: str
    row_count: int
    batch_num: int


@dataclass(frozen=True)
class RelationLookupEvent:
    """关联查找事件.

    Attributes:
        field_key: 当前字段
        row_id: 行标识
        fk_raw: 原始外键
        fk_normalized: 归一化外键
        target_source: 目标源
        result: 关联结果类型
        fk_type: 原始外键类型(可选)
        expected_type: 期望类型(可选)
        error_message: 错误说明(可选)
    """

    field_key: str
    row_id: Hashable
    fk_raw: Any
    fk_normalized: Any
    target_source: str
    result: RelationLookupResult
    fk_type: str | None = None
    expected_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class StageSpanEvent:
    """阶段耗时事件 (loader/compute/write)."""

    stage: str
    batch_num: int
    duration: float


@dataclass(frozen=True)
class AdaptiveSchedulerDecisionEvent:
    """Adaptive scheduler decision event.

    Emitted only in `parallel_mode="adaptive"` when subscribed (wants-gated).
    """

    batch_num: int
    layer_index: int
    decision: str
    backend: str
    reason: str | None = None
    layer_task_count: int | None = None
    process_failure_mode: str | None = None
    pool_limits: dict[str, int] | None = None
    pool_wait_ms_total: dict[str, float] | None = None
    pool_wait_ms_max: dict[str, float] | None = None
    pool_wait_count: dict[str, int] | None = None


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
