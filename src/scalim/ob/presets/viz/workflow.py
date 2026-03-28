import time
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, cast

from ....events import (
    EVENT_WORKFLOW_CACHE_ACQUIRE,
    EVENT_WORKFLOW_CACHE_EVICT,
    EVENT_WORKFLOW_CACHE_RELEASE,
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
    EVENT_WORKFLOW_RESOURCE_COMMIT,
    EVENT_WORKFLOW_RESOURCE_CREATE,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
)
from ....events._events import (
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
from ....spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowResourceIr,
    WriteSheetNodeIr,
)
from ....vendor.dataclassesx import asdict
from ...observer import EventDispatchObserver as _EventDispatchObserver
from .._internal.viz_config import VizObserverConfig
from .._internal.viz_nodes import VizObserverNodeMixin
from .._internal.viz_output import VizObserverOutputMixin

_WORKFLOW_DISPATCH_MAP = {
    EVENT_WORKFLOW_NODE_START: "on_workflow_node_start",
    EVENT_WORKFLOW_NODE_END: "on_workflow_node_end",
    EVENT_WORKFLOW_NODE_CANCELLED: "on_workflow_node_cancelled",
    EVENT_WORKFLOW_CACHE_ACQUIRE: "on_workflow_cache_acquire",
    EVENT_WORKFLOW_CACHE_RELEASE: "on_workflow_cache_release",
    EVENT_WORKFLOW_CACHE_EVICT: "on_workflow_cache_evict",
    EVENT_WORKFLOW_RESOURCE_CREATE: "on_workflow_resource_create",
    EVENT_WORKFLOW_RESOURCE_WRITE: "on_workflow_resource_write",
    EVENT_WORKFLOW_RESOURCE_COMMIT: "on_workflow_resource_commit",
    EVENT_WORKFLOW_RESOURCE_DISCARD: "on_workflow_resource_discard",
    # 工作流运行时额外发出的事件类型(用于回放体验).
    "workflow_started": "on_workflow_started",
    "workflow_finished": "on_workflow_finished",
}


def _as_node_id(value: object) -> str:
    return str(value or "").strip()


def _workflow_node_ref(workflow_node_id: str) -> Dict[str, str]:
    return {"type": "workflow_node", "id": "workflow_node:{}".format(str(workflow_node_id))}


def _workflow_resource_ref(resource_type: str, resource_id: str) -> Dict[str, str]:
    return {
        "type": "workflow_resource",
        "id": "workflow_resource:{}:{}".format(str(resource_type), str(resource_id)),
    }


def _derive_workflow_stage_levels(workflow_ir: WorkflowIr) -> Dict[str, int]:
    node_by_id: Dict[str, WorkflowAnyNodeIr] = {}
    for node in workflow_ir.nodes:
        node_id = _as_node_id(node.node_id)
        if node_id:
            node_by_id[node_id] = node

    visiting: Set[str] = set()
    memo: Dict[str, int] = {}

    def _level(node_id: str) -> int:
        cached = memo.get(node_id)
        if cached is not None:
            return int(cached)
        if node_id in visiting:
            # 环检测回退: 保证布局计算可用.
            return 0
        visiting.add(node_id)
        node = node_by_id.get(node_id)
        deps = node.deps if node is not None else ()
        max_dep = -1
        for dep_id in deps or ():
            dep_key = _as_node_id(dep_id)
            if not dep_key or dep_key == node_id:
                continue
            max_dep = max(max_dep, _level(dep_key))
        visiting.remove(node_id)
        value = max_dep + 1 if max_dep >= 0 else 0
        memo[node_id] = int(value)
        return int(value)

    for node in workflow_ir.nodes:
        node_id = _as_node_id(node.node_id)
        if node_id:
            _ = _level(node_id)

    return memo


def build_workflow_viz_graph_snapshot(  # noqa: C901, PLR0912, PLR0915
    workflow_ir: WorkflowIr,
    *,
    demand_run_id_by_workflow_node_id: Optional[Mapping[str, str]] = None,
    workflow_yaml_path: Optional[str] = None,
) -> Dict[str, Any]:
    """构建与 `scalim-viz` 兼容的工作流级 `VizGraphSnapshot`.

    说明:
    - 工作流节点以 `derived` 节点表示,标识固定为 `workflow_node:{id}`
    - 工作流资源以 `output_target` 节点表示,标识固定为 `workflow_resource:{resource_type}:{resource_id}`
    """

    demand_run_id_by_workflow_node_id = dict(demand_run_id_by_workflow_node_id or {})
    stage_level_by_node_id = _derive_workflow_stage_levels(workflow_ir)

    stage_nodes: Dict[int, List[str]] = {}
    for node_id, level in stage_level_by_node_id.items():
        stage_nodes.setdefault(int(level), []).append(str(node_id))

    stages: List[Dict[str, Any]] = []
    stage_id_by_node_id: Dict[str, str] = {}
    for level in sorted(stage_nodes.keys()):
        stage_id = "wf stage {}".format(level)
        members = sorted(stage_nodes.get(level, []))
        for node_id in members:
            stage_id_by_node_id[str(node_id)] = stage_id
            stages.append(
                {
                    "stage_id": stage_id,
                    "level": int(level),
                    # `layoutSnapshot` 要求这些字段名与 `node.data.field_key` 一致.
                    "field_keys": members,
                }
            )

    nodes: List[Dict[str, Any]] = []
    known_node_ids: Set[str] = set()

    def _add_node(node_id: str, node_type: str, data: Dict[str, Any]) -> None:
        if not node_id or node_id in known_node_ids:
            return
        known_node_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "data": data,
                # `XYFlow` 需要提供一个初始位置; 后续会被布局结果覆盖.
                "position": {"x": 0, "y": 0},
            }
        )

    for node in workflow_ir.nodes:
        workflow_node_id = _as_node_id(node.node_id)
        if not workflow_node_id:
            continue
        node_ref_id = "workflow_node:{}".format(workflow_node_id)
        node_type = str(node.node_type.value)

        kind = "workflow_node"
        demand_path: Optional[str] = None
        if isinstance(node, WorkflowNodeIr) and node.node_type == WorkflowNodeType.DEMAND:
            kind = "workflow_demand"
            demand_path = str(node.demand_path) if node.demand_path is not None else None
        elif isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            kind = "workflow_write"

        data: Dict[str, Any] = {
            "label": workflow_node_id,
            "field_key": workflow_node_id,
            "kind": kind,
            "node_type": node_type,
            "level": int(stage_level_by_node_id.get(workflow_node_id, 0)),
        }
        stage_id = stage_id_by_node_id.get(workflow_node_id)
        if stage_id:
            data["stage_id"] = stage_id

        if demand_path:
            data["demand_path"] = demand_path
        demand_run_id = str(demand_run_id_by_workflow_node_id.get(workflow_node_id, "") or "").strip()
        if kind == "workflow_demand" and demand_run_id:
            data["demand_run_id"] = demand_run_id

        if isinstance(node, WriteSheetNodeIr):
            data.update(
                {
                    "resource_type": str(node.resource_type),
                    "resource_id": str(node.resource_id),
                    "sheet": str(node.sheet),
                    "input_node_id": str(node.input_node_id),
                    "input_output_id": str(node.input_output_id),
                    "on_conflict": str(node.on_conflict),
                }
            )
        elif isinstance(node, AppendSheetNodeIr):
            data.update(
                {
                    "resource_type": str(node.resource_type),
                    "resource_id": str(node.resource_id),
                    "sheet": str(node.sheet) if node.sheet is not None else None,
                    "input_node_id": str(node.input_node_id),
                    "input_output_id": str(node.input_output_id),
                    "align_by": str(node.align_by),
                    "header_policy": str(node.header_policy),
                    "on_mismatch": str(node.on_mismatch),
                }
            )

        _add_node(node_ref_id, "derived", data)

    for res in workflow_ir.resources:
        _append_resource_node(res, add_node=_add_node)

    edges: List[Dict[str, Any]] = []
    edge_keys: Set[Tuple[str, str, str]] = set()

    def _add_edge(source: str, target: str, edge_type: str) -> None:
        if not source or not target or not edge_type:
            return  # pragma: no cover  # pragma: allow-no-cover invariant: edge components validated by callers
        if source not in known_node_ids or target not in known_node_ids:
            return
        key = (source, target, edge_type)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append(
            {
                "id": "e_wf:{}:{}:{}".format(source, target, edge_type),
                "source": source,
                "target": target,
                "type": edge_type,
                "data": {"type": edge_type},
            }
        )

    for node in workflow_ir.nodes:
        workflow_node_id = _as_node_id(node.node_id)
        if not workflow_node_id:
            continue
        node_ref_id = "workflow_node:{}".format(workflow_node_id)
        deps = node.deps or ()
        for dep_id in deps:
            dep_key = _as_node_id(dep_id)
            if not dep_key:
                continue
            dep_ref_id = "workflow_node:{}".format(dep_key)
            _add_edge(dep_ref_id, node_ref_id, "depends_on")

        if isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            resource_type = str(node.resource_type or "").strip()
            resource_id = str(node.resource_id or "").strip()
            if resource_type and resource_id:
                res_node_id = "workflow_resource:{}:{}".format(resource_type, resource_id)
                _add_edge(node_ref_id, res_node_id, "writes_to")

    meta: Dict[str, Any] = {
        "schema_version": "vizgraph/v1",
        "created_at": time.time(),
        "target_fields": [],
        "metadata": {
            "workflow_yaml_path": str(workflow_yaml_path) if workflow_yaml_path is not None else None,
            "workflow_node_count": len([n for n in workflow_ir.nodes if _as_node_id(n.node_id)]),
            "workflow_resource_count": len(workflow_ir.resources),
        },
    }

    return {
        "nodes": sorted(nodes, key=lambda item: str(item.get("id", ""))),
        "edges": sorted(
            edges,
            key=lambda item: (
                str(item.get("source", "")),
                str(item.get("target", "")),
                str(item.get("type", "")),
                str(item.get("id", "")),
            ),
        ),
        "meta": meta,
        "stages": stages,
    }


def _append_resource_node(res: WorkflowResourceIr, *, add_node: Any) -> None:
    resource_id = str(res.resource_id or "").strip()
    resource_type = str(res.resource_type or "").strip()
    if not resource_id or not resource_type:
        return
    node_id = "workflow_resource:{}:{}".format(resource_type, resource_id)
    label = "{}:{}".format(resource_type, resource_id)
    add_node(
        node_id,
        "output_target",
        {
            "label": label,
            "target_id": label,
            "kind": resource_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "path": str(res.path or ""),
        },
    )


class WorkflowVizObserver(VizObserverNodeMixin, VizObserverOutputMixin, _EventDispatchObserver):
    """将工作流作用域事件投影为 `vizevent/v1`,并写入工作流级回放运行."""

    supports_unknown_event_types: bool = True

    dispatch_map: Dict[str, str] = _WORKFLOW_DISPATCH_MAP

    config: VizObserverConfig
    snapshot: Optional[Dict[str, Any]]
    run_id: Optional[str]
    _events_emitter: Any
    _trace_emitter: Any
    _known_node_ids: Optional[Set[str]]
    _node_id_cache: Optional[Dict[str, str]]
    _snapshot_written: bool
    _run_dir_applied: bool
    _node_wall_start_ts: Dict[str, float]
    _workflow_wall_start_ts: Optional[float]

    def __init__(
        self,
        *,
        config: Optional[VizObserverConfig] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config or VizObserverConfig()
        self.snapshot = snapshot
        self.run_id = None
        self._events_emitter = None
        self._trace_emitter = None
        self._known_node_ids = None
        self._node_id_cache = {}
        self._snapshot_written = False
        self._run_dir_applied = False
        self._node_wall_start_ts = {}
        self._workflow_wall_start_ts = None
        self._attach_viz_metadata()

    def _ensure_started(self) -> None:
        if not self.config.is_enabled():
            return
        self._ensure_run_id()
        self._ensure_emitters()

    def _entry_workflow_node_ref_id(self) -> str:
        snapshot = self.snapshot or {}
        nodes = snapshot.get("nodes")
        if isinstance(nodes, list):
            ids: List[str] = []
            for item in cast("List[Dict[str, Any]]", nodes):  # pragma: allow-cast snapshot nodes typed narrowing
                node_id = str(item.get("id") or "").strip()
                if node_id.startswith("workflow_node:"):
                    ids.append(node_id)
            if ids:
                ids.sort()
                return ids[0]
        return "workflow_node:__workflow__"

    def _emit_workflow_event(self, event_type: str, node_ref: Dict[str, str], payload: Dict[str, Any]) -> None:
        if not self.config.is_enabled():
            return
        self._ensure_started()
        self._emit_event(event_type, node_ref, payload)

    def on_workflow_started(self, payload: Any) -> None:
        self._workflow_wall_start_ts = time.time()
        node_ref_id = self._entry_workflow_node_ref_id()
        data: Dict[str, Any]
        if isinstance(payload, dict):
            data = cast("Dict[str, Any]", payload)  # pragma: allow-cast payload dict typed narrowing
        else:
            data = {}
        self._emit_workflow_event(
            "workflow_started",
            {"type": "workflow_node", "id": node_ref_id},
            data,
        )

    def on_workflow_finished(self, payload: Any) -> None:
        node_ref_id = self._entry_workflow_node_ref_id()
        data: Dict[str, Any]
        if isinstance(payload, dict):
            data = cast("Dict[str, Any]", payload)  # pragma: allow-cast payload dict typed narrowing
        else:
            data = {}
        self._emit_workflow_event(
            "workflow_finished",
            {"type": "workflow_node", "id": node_ref_id},
            data,
        )

    def on_workflow_node_start(self, payload: WorkflowNodeStartEvent) -> None:
        node_id = str(payload.workflow_node_id)
        self._node_wall_start_ts[node_id] = time.time()
        self._emit_workflow_event(
            "workflow_node_started",
            _workflow_node_ref(node_id),
            {
                "workflow_exec_id": payload.workflow_exec_id,
                "workflow_node_id": node_id,
                "node_type": payload.node_type,
                "demand_path": payload.demand_path,
            },
        )

    def on_workflow_node_end(self, payload: WorkflowNodeEndEvent) -> None:
        node_id = str(payload.workflow_node_id)
        started = self._node_wall_start_ts.get(node_id)
        duration_ms: Optional[int] = None
        if started is not None:
            duration_ms = int(max(0.0, time.time() - started) * 1000)
        out: Dict[str, Any] = {
            "workflow_exec_id": payload.workflow_exec_id,
            "workflow_node_id": node_id,
            "node_type": payload.node_type,
            "status": payload.status,
            "demand_path": payload.demand_path,
            "error_type": payload.error_type,
            "error_message": payload.error_message,
        }
        if duration_ms is not None:
            out["duration_ms"] = duration_ms
        self._emit_workflow_event(
            "workflow_node_completed",
            _workflow_node_ref(node_id),
            out,
        )

    def on_workflow_node_cancelled(self, payload: WorkflowNodeCancelledEvent) -> None:
        node_id = str(payload.workflow_node_id)
        self._emit_workflow_event(
            "workflow_node_cancelled",
            _workflow_node_ref(node_id),
            {
                "workflow_exec_id": payload.workflow_exec_id,
                "workflow_node_id": node_id,
                "node_type": payload.node_type,
                "reason": payload.reason,
                "message": payload.message,
                "demand_path": payload.demand_path,
            },
        )

    def on_workflow_cache_acquire(self, payload: WorkflowCacheAcquireEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_CACHE_ACQUIRE,
            _workflow_node_ref(str(payload.workflow_node_id)),
            asdict(payload),
        )

    def on_workflow_cache_release(self, payload: WorkflowCacheReleaseEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_CACHE_RELEASE,
            _workflow_node_ref(str(payload.workflow_node_id)),
            asdict(payload),
        )

    def on_workflow_cache_evict(self, payload: WorkflowCacheEvictEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_CACHE_EVICT,
            _workflow_node_ref(str(payload.workflow_node_id)),
            asdict(payload),
        )

    def on_workflow_resource_create(self, payload: WorkflowResourceCreateEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_RESOURCE_CREATE,
            _workflow_resource_ref(payload.resource_type, payload.resource_id),
            asdict(payload),
        )

    def on_workflow_resource_write(self, payload: WorkflowResourceWriteEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_RESOURCE_WRITE,
            _workflow_resource_ref(payload.resource_type, payload.resource_id),
            asdict(payload),
        )

    def on_workflow_resource_commit(self, payload: WorkflowResourceCommitEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_RESOURCE_COMMIT,
            _workflow_resource_ref(payload.resource_type, payload.resource_id),
            asdict(payload),
        )

    def on_workflow_resource_discard(self, payload: WorkflowResourceDiscardEvent) -> None:
        self._emit_workflow_event(
            EVENT_WORKFLOW_RESOURCE_DISCARD,
            _workflow_resource_ref(payload.resource_type, payload.resource_id),
            asdict(payload),
        )


__all__ = [
    "WorkflowVizObserver",
    "build_workflow_viz_graph_snapshot",
]
