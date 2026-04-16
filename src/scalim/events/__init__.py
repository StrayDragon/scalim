"""事件类型与辅助工具.

对外推荐优先从包根导入稳定事件契约(避免绑定到内部模块文件名),例如:
- `from scalim.events import Event, EventType, get_event_catalog`

类型化 `payload` 数据类属于内部实现细节,不作为公共导入契约.
"""

# pragma: scalim-public-api tier1:110:scalim.events|事件envelope+事件类型入口+事件目录查询入口|写 Observer/Hook;按 `event_type` 订阅/过滤
# pragma: scalim-public-api tier1:111:scalim.events.type_groups|事件类型分组视图|按主题探索 `EventType`(不引入新值)

from .api import (
    WORKFLOW_ATTRIBUTION_META_KEYS,
    WORKFLOW_EXEC_ID_META_KEY,
    WORKFLOW_NODE_ID_META_KEY,
    Event,
    EventDescriptor,
    EventType,
    WorkflowNodeCancelledReason,
    WorkflowNodeEndStatus,
    generate_run_id,
    get_event_catalog,
    get_event_catalog_map,
    now_ts,
)

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
)
