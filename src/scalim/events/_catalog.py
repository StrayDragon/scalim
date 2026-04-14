# region imports

from typing import Dict, List, Sequence

from ..vendor.dataclassesx import dataclass
from ._events import (
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
    OperatorSpanEvent,
    OutputTargetEndEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
    WorkflowCacheAcquireEvent,
    WorkflowCacheEvictEvent,
    WorkflowCacheReleaseEvent,
    WorkflowNodeCancelledEvent,
    WorkflowNodeEndEvent,
    WorkflowNodeStartEvent,
    WorkflowResourceCommitEvent,
    WorkflowResourceCreateEvent,
    WorkflowResourceDiscardEvent,
    WorkflowResourceWriteEvent,
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
EVENT_OPERATOR_SPAN = "operator_span"
EVENT_ADAPTIVE_SCHEDULER_DECISION = "adaptive_scheduler_decision"
EVENT_OUTPUT_TARGET_END = "output_target_end"

# 策略决策 `signal`(默认不进入公共事件目录).
#
# 该类 `signal` 在运行期边界(例如 `pre-run_ir`)触发,用于允许 `hook` 改写派生的运行期策略值.
EVENT_PRE_USE_BATCH_SIZE = "pre_use_batch_size"

EVENT_WORKFLOW_NODE_START = "workflow_node_start"
EVENT_WORKFLOW_NODE_END = "workflow_node_end"
EVENT_WORKFLOW_NODE_CANCELLED = "workflow_node_cancelled"

EVENT_WORKFLOW_CACHE_ACQUIRE = "workflow_cache_acquire"
EVENT_WORKFLOW_CACHE_RELEASE = "workflow_cache_release"
EVENT_WORKFLOW_CACHE_EVICT = "workflow_cache_evict"

EVENT_WORKFLOW_RESOURCE_CREATE = "workflow_resource_create"
EVENT_WORKFLOW_RESOURCE_WRITE = "workflow_resource_write"
EVENT_WORKFLOW_RESOURCE_COMMIT = "workflow_resource_commit"
EVENT_WORKFLOW_RESOURCE_DISCARD = "workflow_resource_discard"

WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED = "dependency_failed"
WORKFLOW_NODE_CANCELLED_REASON_UPSTREAM_CANCELLED = "upstream_cancelled"
WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL = "policy_all_fail"

WORKFLOW_NODE_END_STATUS_OK = "ok"
WORKFLOW_NODE_END_STATUS_ERROR = "error"

WORKFLOW_EVENT_PREFIX_NODE = "workflow_node_"
WORKFLOW_EVENT_PREFIX_CACHE = "workflow_cache_"
WORKFLOW_EVENT_PREFIX_RESOURCE = "workflow_resource_"
WORKFLOW_EVENT_PREFIXES = (
    WORKFLOW_EVENT_PREFIX_NODE,
    WORKFLOW_EVENT_PREFIX_CACHE,
    WORKFLOW_EVENT_PREFIX_RESOURCE,
)


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
        name=EVENT_OPERATOR_SPAN,
        summary="operator 耗时",
        key_fields=("operator_type", "field_key", "batch_num", "duration"),
        volume="lite",
        payload_policy="full",
        payload_type=OperatorSpanEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_ADAPTIVE_SCHEDULER_DECISION,
        summary="adaptive 调度决策",
        key_fields=("batch_num", "layer_index", "decision", "backend"),
        volume="lite",
        payload_policy="full",
        payload_type=AdaptiveSchedulerDecisionEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_OUTPUT_TARGET_END,
        summary="输出目标结束统计",
        key_fields=("target_id", "output_path", "sheet_name", "row_count", "error_count"),
        volume="lite",
        payload_policy="full",
        payload_type=OutputTargetEndEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_NODE_START,
        summary="workflow 节点开始",
        key_fields=("workflow_node_id", "node_type"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowNodeStartEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_NODE_END,
        summary="workflow 节点结束",
        key_fields=("workflow_node_id", "node_type", "status"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowNodeEndEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_NODE_CANCELLED,
        summary="workflow 节点取消",
        key_fields=("workflow_node_id", "node_type", "reason"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowNodeCancelledEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_CACHE_ACQUIRE,
        summary="workflow cache acquire",
        key_fields=("workflow_node_id", "cache_kind", "source_id", "cache_status"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowCacheAcquireEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_CACHE_RELEASE,
        summary="workflow cache release",
        key_fields=("workflow_node_id", "cache_kind", "source_id", "remaining_consumers"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowCacheReleaseEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_CACHE_EVICT,
        summary="workflow cache evict",
        key_fields=("workflow_node_id", "cache_kind", "source_id", "reason"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowCacheEvictEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_RESOURCE_CREATE,
        summary="workflow resource create",
        key_fields=("workflow_node_id", "resource_type", "resource_id"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowResourceCreateEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_RESOURCE_WRITE,
        summary="workflow resource write",
        key_fields=("workflow_node_id", "resource_type", "resource_id", "write_kind", "action"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowResourceWriteEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_RESOURCE_COMMIT,
        summary="workflow resource commit",
        key_fields=("workflow_node_id", "resource_type", "resource_id"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowResourceCommitEvent.__name__,
    ),
    EventDescriptor(
        name=EVENT_WORKFLOW_RESOURCE_DISCARD,
        summary="workflow resource discard",
        key_fields=("workflow_node_id", "resource_type", "resource_id", "reason"),
        volume="lite",
        payload_policy="full",
        payload_type=WorkflowResourceDiscardEvent.__name__,
    ),
]


def get_event_catalog() -> List[EventDescriptor]:
    return list(_EVENT_CATALOG)


def get_event_catalog_map() -> Dict[str, EventDescriptor]:
    return {item.name: item for item in _EVENT_CATALOG}


__all__ = ()
