"""`events` 对外稳定导出面.

说明:
- 对外稳定导入路径为 `scalim.events`.
- 进程内事件身份以 `EventType` 为唯一来源;成员值为稳定字符串,边界编码可使用 `.value`.
- 类型化 `payload` 数据类由 `scalim.events` 公开再导出;具体实现仍可在私有模块中.
"""

from enum import Enum
from typing import Any, Dict

from ..vendor.compact.typing_extensionsx import override
from ..vendor.dataclassesx import asdict, dataclass, field, is_dataclass
from ._attribution import WORKFLOW_ATTRIBUTION_META_KEYS, WORKFLOW_EXEC_ID_META_KEY, WORKFLOW_NODE_ID_META_KEY
from ._catalog import (
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_COLUMN_WRITE,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_ERROR,
    EVENT_FIELD_COMPUTE,
    EVENT_FIELD_SLIM,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_LOADER_SLIM,
    EVENT_OPERATOR_SPAN,
    EVENT_OUTPUT_TARGET_END,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_PRE_USE_BATCH_SIZE,
    EVENT_RELATION_LOOKUP,
    EVENT_ROW_RELEASE,
    EVENT_ROW_WRITE,
    EVENT_STAGE_SPAN,
    EVENT_WORKFLOW_CACHE_ACQUIRE,
    EVENT_WORKFLOW_CACHE_EVICT,
    EVENT_WORKFLOW_CACHE_RELEASE,
    EVENT_WORKFLOW_FINISHED,
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
    EVENT_WORKFLOW_RESOURCE_COMMIT,
    EVENT_WORKFLOW_RESOURCE_CREATE,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
    EVENT_WORKFLOW_STARTED,
    WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED,
    WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL,
    WORKFLOW_NODE_CANCELLED_REASON_UPSTREAM_CANCELLED,
    WORKFLOW_NODE_END_STATUS_ERROR,
    WORKFLOW_NODE_END_STATUS_OK,
    EventDescriptor,
    get_event_catalog,
    get_event_catalog_map,
)
from ._event import generate_run_id, now_ts


class EventType(str, Enum):
    """稳定事件类型枚举(进程内事件身份 `SSOT`;值为稳定字符串)."""

    PIPELINE_START = EVENT_PIPELINE_START
    PIPELINE_END = EVENT_PIPELINE_END
    BATCH_START = EVENT_BATCH_START
    BATCH_END = EVENT_BATCH_END
    LOADER_CALL = EVENT_LOADER_CALL
    LOADER_RETRY = EVENT_LOADER_RETRY
    FIELD_COMPUTE = EVENT_FIELD_COMPUTE
    ERROR = EVENT_ERROR
    DIAGNOSTIC_WARNING = EVENT_DIAGNOSTIC_WARNING
    FIELD_SLIM = EVENT_FIELD_SLIM
    ROW_WRITE = EVENT_ROW_WRITE
    ROW_RELEASE = EVENT_ROW_RELEASE
    LOADER_SLIM = EVENT_LOADER_SLIM
    COLUMN_WRITE = EVENT_COLUMN_WRITE
    RELATION_LOOKUP = EVENT_RELATION_LOOKUP
    STAGE_SPAN = EVENT_STAGE_SPAN
    OPERATOR_SPAN = EVENT_OPERATOR_SPAN
    ADAPTIVE_SCHEDULER_DECISION = EVENT_ADAPTIVE_SCHEDULER_DECISION
    OUTPUT_TARGET_END = EVENT_OUTPUT_TARGET_END

    # 策略 `signal`(默认不进入公共事件目录).
    PRE_USE_BATCH_SIZE = EVENT_PRE_USE_BATCH_SIZE

    WORKFLOW_STARTED = EVENT_WORKFLOW_STARTED
    WORKFLOW_FINISHED = EVENT_WORKFLOW_FINISHED

    WORKFLOW_NODE_START = EVENT_WORKFLOW_NODE_START
    WORKFLOW_NODE_END = EVENT_WORKFLOW_NODE_END
    WORKFLOW_NODE_CANCELLED = EVENT_WORKFLOW_NODE_CANCELLED

    WORKFLOW_CACHE_ACQUIRE = EVENT_WORKFLOW_CACHE_ACQUIRE
    WORKFLOW_CACHE_RELEASE = EVENT_WORKFLOW_CACHE_RELEASE
    WORKFLOW_CACHE_EVICT = EVENT_WORKFLOW_CACHE_EVICT

    WORKFLOW_RESOURCE_CREATE = EVENT_WORKFLOW_RESOURCE_CREATE
    WORKFLOW_RESOURCE_WRITE = EVENT_WORKFLOW_RESOURCE_WRITE
    WORKFLOW_RESOURCE_COMMIT = EVENT_WORKFLOW_RESOURCE_COMMIT
    WORKFLOW_RESOURCE_DISCARD = EVENT_WORKFLOW_RESOURCE_DISCARD

    @override
    def __str__(self) -> str:
        return str(self.value)


def parse_event_type(value: Any) -> EventType:
    """将边界字符串归一为 `EventType`(宽进仅用于落盘/`JSONL`/`viz` 读回).

    公开注册/订阅作者面必须直接使用 `EventType`,不得依赖本函数绕过严进.
    """
    if isinstance(value, EventType):
        return value
    if type(value) is not str:
        msg = "event_type must be EventType or builtin str; got {}".format(type(value).__name__)
        raise TypeError(msg)
    try:
        return EventType(value)
    except ValueError:
        allowed = sorted(member.value for member in EventType)
        msg = "unknown event_type {!r}; allowed={}".format(value, allowed)
        raise ValueError(msg) from None


@dataclass(frozen=True)
class Event:
    """观察事件统一封装.

    说明:
        - `event_type` 进程内身份为 `EventType`.
        - `seq` 在同一个 `ObserverManager`/`run_id` 内单调递增,不是全局顺序.
        - 在线程/进程/异步并发中,`seq` 仅保证局部有序,事件可能交错.
        - 需要并发上下文时,请通过 `meta` 传递 `worker_id`、`batch_num` 等信息.
    """

    event_type: EventType
    """事件类型(`EventType`;进程内身份 `SSOT`)."""

    timestamp: float
    """事件发出时的 `Unix` 时间戳(秒)."""

    run_id: str
    """一次执行的运行标识."""

    payload: Any
    """事件负载(数据类或原始数据)."""

    meta: Dict[str, Any] = field(default_factory=dict)
    """可选元数据,用于传输/调试/并发上下文提示."""

    seq: int = 0
    """发送端序号 (0 表示未设置; 由 `ObserverManager` 填充)."""

    def to_dict(self) -> Dict[str, Any]:
        payload = self.payload
        if is_dataclass(payload):
            payload = asdict(payload)
        result: Dict[str, Any] = {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "payload": payload,
            "meta": dict(self.meta) if self.meta else {},
            "seq": self.seq,
        }
        return result


class WorkflowNodeEndStatus(str, Enum):
    """`workflow` 节点结束状态枚举(值保持不变)."""

    OK = WORKFLOW_NODE_END_STATUS_OK
    ERROR = WORKFLOW_NODE_END_STATUS_ERROR

    @override
    def __str__(self) -> str:
        return str(self.value)


class WorkflowNodeCancelledReason(str, Enum):
    """`workflow` 节点取消原因枚举(值保持不变)."""

    DEPENDENCY_FAILED = WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED
    UPSTREAM_CANCELLED = WORKFLOW_NODE_CANCELLED_REASON_UPSTREAM_CANCELLED
    POLICY_ALL_FAIL = WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL

    @override
    def __str__(self) -> str:
        return str(self.value)


__all__ = (
    "WORKFLOW_ATTRIBUTION_META_KEYS",
    "WORKFLOW_EXEC_ID_META_KEY",
    "WORKFLOW_NODE_ID_META_KEY",
    "Event",
    "EventDescriptor",
    "EventType",
    "WorkflowNodeCancelledReason",
    "WorkflowNodeEndStatus",
    "generate_run_id",
    "get_event_catalog",
    "get_event_catalog_map",
    "now_ts",
    "parse_event_type",
)
