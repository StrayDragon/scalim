"""事件类型分组视图(仅提升可发现性).

说明:
- 本模块不引入新的事件类型,仅对 `EventType` 做确定性分组.
- 分组不改变事件分发热路径语义;仍以 `event_type` 字符串进行订阅/过滤.
"""

from types import SimpleNamespace

from .api import EventType

workflow = SimpleNamespace(
    started=EventType.WORKFLOW_STARTED,
    finished=EventType.WORKFLOW_FINISHED,
    node=SimpleNamespace(
        start=EventType.WORKFLOW_NODE_START,
        end=EventType.WORKFLOW_NODE_END,
        cancelled=EventType.WORKFLOW_NODE_CANCELLED,
    ),
    cache=SimpleNamespace(
        acquire=EventType.WORKFLOW_CACHE_ACQUIRE,
        release=EventType.WORKFLOW_CACHE_RELEASE,
        evict=EventType.WORKFLOW_CACHE_EVICT,
    ),
    resource=SimpleNamespace(
        create=EventType.WORKFLOW_RESOURCE_CREATE,
        write=EventType.WORKFLOW_RESOURCE_WRITE,
        commit=EventType.WORKFLOW_RESOURCE_COMMIT,
        discard=EventType.WORKFLOW_RESOURCE_DISCARD,
    ),
)

pipeline = SimpleNamespace(
    start=EventType.PIPELINE_START,
    end=EventType.PIPELINE_END,
)

batch = SimpleNamespace(
    start=EventType.BATCH_START,
    end=EventType.BATCH_END,
)

loader = SimpleNamespace(
    call=EventType.LOADER_CALL,
    retry=EventType.LOADER_RETRY,
    slim=EventType.LOADER_SLIM,
)

field = SimpleNamespace(
    compute=EventType.FIELD_COMPUTE,
    slim=EventType.FIELD_SLIM,
)

row = SimpleNamespace(
    write=EventType.ROW_WRITE,
    release=EventType.ROW_RELEASE,
)

column = SimpleNamespace(write=EventType.COLUMN_WRITE)
relation = SimpleNamespace(lookup=EventType.RELATION_LOOKUP)
stage = SimpleNamespace(span=EventType.STAGE_SPAN)
operator = SimpleNamespace(span=EventType.OPERATOR_SPAN)
adaptive = SimpleNamespace(scheduler_decision=EventType.ADAPTIVE_SCHEDULER_DECISION)
output = SimpleNamespace(target_end=EventType.OUTPUT_TARGET_END)
diagnostic = SimpleNamespace(warning=EventType.DIAGNOSTIC_WARNING)
error = SimpleNamespace(error=EventType.ERROR)
pre = SimpleNamespace(use_batch_size=EventType.PRE_USE_BATCH_SIZE)

__all__ = (
    "adaptive",
    "batch",
    "column",
    "diagnostic",
    "error",
    "field",
    "loader",
    "operator",
    "output",
    "pipeline",
    "pre",
    "relation",
    "row",
    "stage",
    "workflow",
)
