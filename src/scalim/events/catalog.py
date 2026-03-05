# region imports

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .events import (
    AdaptiveSchedulerDecisionEvent,
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderRetryEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)

# endregion

EVENT_PIPELINE_START = "pipeline_start"
EVENT_PIPELINE_END = "pipeline_end"
EVENT_BATCH_START = "batch_start"
EVENT_BATCH_END = "batch_end"
EVENT_LOADER_CALL = "loader_call"
EVENT_LOADER_RETRY = "loader_retry"
EVENT_FIELD_COMPUTE = "field_compute"
EVENT_ERROR = "error"
EVENT_DIAGNOSTIC_WARNING = "diagnostic_warning"
EVENT_FIELD_SLIM = "field_slim"
EVENT_ROW_WRITE = "row_write"
EVENT_ROW_RELEASE = "row_release"
EVENT_LOADER_SLIM = "loader_slim"
EVENT_COLUMN_WRITE = "column_write"
EVENT_RELATION_LOOKUP = "relation_lookup"
EVENT_STAGE_SPAN = "stage_span"
EVENT_ADAPTIVE_SCHEDULER_DECISION = "adaptive_scheduler_decision"


@dataclass(frozen=True)
class EventDescriptor:
    name: str
    """事件名称(来自事件目录常量)."""

    summary: str
    """事件摘要(用于展示/日志)."""

    key_fields: Sequence[str]
    """关键字段列表(用于展示/索引)."""

    volume: str
    """事件量级(例如 `lite`/`full`)."""

    payload_policy: str
    """负载策略(例如 `full` 或 `summary|sample|full|none`)."""

    payload_type: str
    """负载类型名称(通常为事件数据类名)."""


_EVENT_CATALOG: List[EventDescriptor] = [
    EventDescriptor(
        name=EVENT_PIPELINE_START,
        summary="pipeline 启动",
        key_fields=("targets", "batch_size"),
        volume="lite",
        payload_policy="full",
        payload_type=PipelineStartEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_PIPELINE_END,
        summary="pipeline 结束",
        key_fields=("total_batches", "total_duration"),
        volume="lite",
        payload_policy="full",
        payload_type=PipelineEndEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_BATCH_START,
        summary="批次开始",
        key_fields=("batch_num", "row_ids"),
        volume="lite",
        payload_policy="full",
        payload_type=BatchStartEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_BATCH_END,
        summary="批次结束",
        key_fields=("batch_num", "duration"),
        volume="lite",
        payload_policy="full",
        payload_type=BatchEndEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_LOADER_CALL,
        summary="loader 调用",
        key_fields=("loader_name", "duration", "cache_status"),
        volume="full",
        payload_policy="summary|sample|full|none",
        payload_type=LoaderCallEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_LOADER_RETRY,
        summary="loader 重试",
        key_fields=("loader_name", "attempt_num", "sleep_seconds"),
        volume="lite",
        payload_policy="full",
        payload_type=LoaderRetryEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_FIELD_COMPUTE,
        summary="字段计算",
        key_fields=("field_key", "row_id"),
        volume="full",
        payload_policy="full",
        payload_type=FieldComputeEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_ERROR,
        summary="执行错误",
        key_fields=("error", "context"),
        volume="lite",
        payload_policy="full",
        payload_type=ErrorEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_DIAGNOSTIC_WARNING,
        summary="诊断告警",
        key_fields=("message", "source_id", "field_id"),
        volume="lite",
        payload_policy="full",
        payload_type=DiagnosticWarningEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_FIELD_SLIM,
        summary="字段瘦身",
        key_fields=("field_key", "batch_num"),
        volume="lite",
        payload_policy="full",
        payload_type=FieldSlimEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_ROW_WRITE,
        summary="行写入",
        key_fields=("row_id", "batch_num"),
        volume="full",
        payload_policy="full",
        payload_type=RowWriteEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_ROW_RELEASE,
        summary="行释放",
        key_fields=("row_id", "batch_num"),
        volume="full",
        payload_policy="full",
        payload_type=RowReleaseEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_LOADER_SLIM,
        summary="loader 结果瘦身",
        key_fields=("loader_name", "batch_num"),
        volume="lite",
        payload_policy="full",
        payload_type=LoaderSlimEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_COLUMN_WRITE,
        summary="列写入",
        key_fields=("field_key", "batch_num"),
        volume="lite",
        payload_policy="full",
        payload_type=ColumnWriteEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_RELATION_LOOKUP,
        summary="关联查找",
        key_fields=("field_key", "row_id", "target_source"),
        volume="full",
        payload_policy="full",
        payload_type=RelationLookupEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_STAGE_SPAN,
        summary="阶段耗时",
        key_fields=("stage", "batch_num", "duration"),
        volume="lite",
        payload_policy="full",
        payload_type=StageSpanEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_ADAPTIVE_SCHEDULER_DECISION,
        summary="adaptive 调度决策",
        key_fields=("batch_num", "layer_index", "decision", "backend"),
        volume="lite",
        payload_policy="full",
        payload_type=AdaptiveSchedulerDecisionEvent.__name__,
    ),
]


def get_event_catalog() -> List[EventDescriptor]:
    return list(_EVENT_CATALOG)


def get_event_catalog_map() -> Dict[str, EventDescriptor]:
    return {item.name: item for item in _EVENT_CATALOG}


__all__ = [
    "EVENT_ADAPTIVE_SCHEDULER_DECISION",
    "EVENT_BATCH_END",
    "EVENT_BATCH_START",
    "EVENT_COLUMN_WRITE",
    "EVENT_DIAGNOSTIC_WARNING",
    "EVENT_ERROR",
    "EVENT_FIELD_COMPUTE",
    "EVENT_FIELD_SLIM",
    "EVENT_LOADER_CALL",
    "EVENT_LOADER_RETRY",
    "EVENT_LOADER_SLIM",
    "EVENT_PIPELINE_END",
    "EVENT_PIPELINE_START",
    "EVENT_RELATION_LOOKUP",
    "EVENT_ROW_RELEASE",
    "EVENT_ROW_WRITE",
    "EVENT_STAGE_SPAN",
    "EventDescriptor",
    "get_event_catalog",
    "get_event_catalog_map",
]
