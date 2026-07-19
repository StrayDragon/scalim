from typing import Dict, List, Set

from ...events import (
    Event,
    EventType,
)
from ...vendor.dataclassesx import dataclass

__all__ = ()


@dataclass(frozen=True)
class WorkflowReplayEventBuckets:
    started_events: List[Event]
    finished_events: List[Event]
    other_global_events: List[Event]
    unknown_node_events: List[Event]
    resource_commit_events: List[Event]
    node_start_events_by_node_id: Dict[str, List[Event]]
    node_end_events_by_node_id: Dict[str, List[Event]]
    node_cancelled_events_by_node_id: Dict[str, List[Event]]
    node_other_events_by_node_id: Dict[str, List[Event]]


def _workflow_event_workflow_node_id(event: Event) -> str:
    meta = event.meta
    if not meta or not isinstance(meta, dict):
        return ""
    raw_node_id = meta.get("workflow_node_id")
    if raw_node_id is None:
        return ""
    return str(raw_node_id).strip()


def classify_workflow_events_for_replay(workflow_events: List[Event], *, known_node_ids: Set[str]) -> WorkflowReplayEventBuckets:
    """将工作流捕获的事件按回放所需语义做分类/分桶(纯数据整形)."""

    started_events: List[Event] = []
    finished_events: List[Event] = []
    other_global_events: List[Event] = []
    unknown_node_events: List[Event] = []
    resource_commit_events: List[Event] = []

    node_start_events_by_node_id: Dict[str, List[Event]] = {}
    node_end_events_by_node_id: Dict[str, List[Event]] = {}
    node_cancelled_events_by_node_id: Dict[str, List[Event]] = {}
    node_other_events_by_node_id: Dict[str, List[Event]] = {}

    global_buckets: Dict[str, List[Event]] = {
        str(EventType.WORKFLOW_STARTED): started_events,
        str(EventType.WORKFLOW_FINISHED): finished_events,
        str(EventType.WORKFLOW_RESOURCE_COMMIT): resource_commit_events,
    }

    node_event_buckets: Dict[str, Dict[str, List[Event]]] = {
        str(EventType.WORKFLOW_NODE_START): node_start_events_by_node_id,
        str(EventType.WORKFLOW_NODE_END): node_end_events_by_node_id,
        str(EventType.WORKFLOW_NODE_CANCELLED): node_cancelled_events_by_node_id,
    }

    for event in workflow_events:
        event_type = str(event.event_type)
        bucket = global_buckets.get(event_type)
        if bucket is not None:
            bucket.append(event)
            continue

        node_id = _workflow_event_workflow_node_id(event)
        if not node_id:
            other_global_events.append(event)
            continue
        if node_id not in known_node_ids:
            unknown_node_events.append(event)
            continue

        node_bucket = node_event_buckets.get(event_type)
        if node_bucket is None:
            node_other_events_by_node_id.setdefault(node_id, []).append(event)
        else:
            node_bucket.setdefault(node_id, []).append(event)

    return WorkflowReplayEventBuckets(
        started_events=started_events,
        finished_events=finished_events,
        other_global_events=other_global_events,
        unknown_node_events=unknown_node_events,
        resource_commit_events=resource_commit_events,
        node_start_events_by_node_id=node_start_events_by_node_id,
        node_end_events_by_node_id=node_end_events_by_node_id,
        node_cancelled_events_by_node_id=node_cancelled_events_by_node_id,
        node_other_events_by_node_id=node_other_events_by_node_id,
    )
