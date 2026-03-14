# region imports

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast

from ...planning.plan import ExecutionPlan
from ..observer import EventDispatchObserver
from ._internal.viz_config import VizObserverConfig
from ._internal.viz_handlers import VizObserverHandlerMixin
from ._internal.viz_nodes import VizObserverNodeMixin
from ._internal.viz_output import VizEventEmitter, VizObserverOutputMixin

# endregion


def _get_snapshot_node_ids(snapshot: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    nodes_value = snapshot.get("nodes")
    if not isinstance(nodes_value, list):
        return ids
    nodes = cast("List[Dict[str, Any]]", nodes_value)
    for item in nodes:
        node_id = item.get("id")
        if node_id:
            ids.add(str(node_id))
    return ids


def _ensure_snapshot_list(snapshot: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = snapshot.get(key)
    if isinstance(value, list):
        return cast("List[Dict[str, Any]]", value)
    out: List[Dict[str, Any]] = []
    snapshot[key] = out
    return out


def _get_snapshot_edge_keys(edges: List[Dict[str, Any]]) -> Set[Tuple[str, str, str]]:
    keys: Set[Tuple[str, str, str]] = set()
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        edge_type = str(edge.get("type") or "")
        if source and target and edge_type:
            keys.add((source, target, edge_type))
    return keys


def _as_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return text


def _describe_output_spec(output: Any) -> Tuple[Optional[str], Optional[str]]:
    if output is None:
        return None, None
    output_path = _as_optional_text(getattr(output, "path", None))
    sheet_name = _as_optional_text(getattr(output, "sheet_name", None))
    return output_path, sheet_name


def _append_output_target_nodes_for_targets(
    nodes: List[Dict[str, Any]],
    node_ids: Set[str],
    *,
    targets: Iterable[Any],
    kind: str,
) -> None:
    for target in targets:
        target_id = _as_optional_text(getattr(target, "target_id", None))
        if not target_id:
            continue
        output_path, sheet_name = _describe_output_spec(getattr(target, "output", None))
        _add_output_target_node(
            nodes,
            node_ids,
            target_id=target_id,
            kind=kind,
            output_path=output_path,
            sheet_name=sheet_name,
            is_primary=bool(getattr(target, "is_primary", False)),
        )


def _append_output_target_node_for_sheet(
    nodes: List[Dict[str, Any]],
    node_ids: Set[str],
    *,
    sheet: Any,
    kind: str,
) -> None:
    target_id = _as_optional_text(getattr(sheet, "target_id", None))
    if not target_id:
        return
    output_path, _sheet_name = _describe_output_spec(getattr(sheet, "output", None))
    sheet_name = _as_optional_text(getattr(sheet, "sheet_name", None))
    _add_output_target_node(
        nodes,
        node_ids,
        target_id=target_id,
        kind=kind,
        output_path=output_path,
        sheet_name=sheet_name or _sheet_name,
        is_primary=False,
    )


def _append_output_target_edges_for_direct_targets(
    edges: List[Dict[str, Any]],
    edge_keys: Set[Tuple[str, str, str]],
    node_ids: Set[str],
    *,
    targets: Iterable[Any],
) -> None:
    for target in targets:
        target_id = _as_optional_text(getattr(target, "target_id", None))
        if not target_id:
            continue
        layout = getattr(target, "layout", None)
        field_ids = getattr(layout, "field_ids", None) if layout is not None else None
        if field_ids is None:
            continue
        requires = getattr(target, "requires", None)
        for field_id in _iter_unique_field_ids(cast("Iterable[str]", field_ids), requires):
            _maybe_add_output_target_edge(edges, edge_keys, node_ids, source_field_id=field_id, target_id=target_id)


def _append_output_target_edges_for_derived_targets(
    edges: List[Dict[str, Any]],
    edge_keys: Set[Tuple[str, str, str]],
    node_ids: Set[str],
    *,
    targets: Iterable[Any],
) -> None:
    for target in targets:
        target_id = _as_optional_text(getattr(target, "target_id", None))
        if not target_id:
            continue
        derived = getattr(target, "derived", None)
        if derived is None or not hasattr(derived, "required_fields"):
            continue
        required_fields = derived.required_fields()  # type: ignore[no-any-call]
        requires = getattr(target, "requires", None)
        for field_id in _iter_unique_field_ids(cast("Iterable[str]", required_fields), requires):
            _maybe_add_output_target_edge(edges, edge_keys, node_ids, source_field_id=field_id, target_id=target_id)


def _sort_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(nodes, key=lambda item: str(item.get("id", "")))


def _sort_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def edge_key(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
        return (
            str(item.get("source", "")),
            str(item.get("target", "")),
            str(item.get("type", "")),
            str(item.get("id", "")),
        )

    return sorted(edges, key=edge_key)


def _add_output_target_node(
    nodes: List[Dict[str, Any]],
    node_ids: Set[str],
    *,
    target_id: str,
    kind: str,
    output_path: Optional[str],
    sheet_name: Optional[str],
    is_primary: bool,
) -> None:
    node_id = "output_target:{}".format(target_id)
    if node_id in node_ids:
        return
    node_ids.add(node_id)
    data: Dict[str, Any] = {
        "label": str(target_id),
        "target_id": str(target_id),
        "kind": str(kind),
        "is_primary": bool(is_primary),
    }
    if output_path:
        data["output_path"] = str(output_path)
    if sheet_name:
        data["sheet_name"] = str(sheet_name)
    nodes.append(
        {
            "id": node_id,
            "type": "output_target",
            "data": data,
            # `XYFlow` 需要 `position`,这里使用占位值.
            "position": {"x": 0, "y": 0},
        }
    )


def _iter_unique_field_ids(field_ids: Iterable[str], requires: Optional[Tuple[str, ...]]) -> Tuple[str, ...]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for item in list(field_ids) + list(requires or ()):
        key = str(item)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return tuple(ordered)


def _maybe_add_output_target_edge(
    edges: List[Dict[str, Any]],
    edge_keys: Set[Tuple[str, str, str]],
    node_ids: Set[str],
    *,
    source_field_id: str,
    target_id: str,
) -> None:
    source = "field:{}".format(source_field_id)
    target = "output_target:{}".format(target_id)
    edge_type = "composed_from"
    if source not in node_ids or target not in node_ids:
        return
    key = (source, target, edge_type)
    if key in edge_keys:
        return
    edge_keys.add(key)
    edges.append(
        {
            "id": "e_out:{}:{}:{}".format(source, target, edge_type),
            "source": source,
            "target": target,
            "type": edge_type,
            "data": {"type": edge_type},
        }
    )


def augment_viz_graph_snapshot_for_output_composition(
    snapshot: Dict[str, Any],
    *,
    output_composition: Any,
) -> Dict[str, Any]:
    """对 `VizGraphSnapshot` 做最小增强:追加 `output_target:*` 节点与 `composed_from` 边."""

    if not snapshot or not isinstance(snapshot, dict):
        return snapshot

    nodes = _ensure_snapshot_list(snapshot, "nodes")
    edges = _ensure_snapshot_list(snapshot, "edges")

    node_ids = _get_snapshot_node_ids(snapshot)
    edge_keys = _get_snapshot_edge_keys(edges)

    targets = getattr(output_composition, "targets", None) or ()
    derived_targets = getattr(output_composition, "derived_targets", None) or ()
    meta_sheet = getattr(output_composition, "meta_sheet", None)
    audit_sheet = getattr(output_composition, "audit_sheet", None)

    _append_output_target_nodes_for_targets(nodes, node_ids, targets=targets, kind="direct")
    _append_output_target_nodes_for_targets(nodes, node_ids, targets=derived_targets, kind="derived")
    if meta_sheet is not None:
        _append_output_target_node_for_sheet(nodes, node_ids, sheet=meta_sheet, kind="meta_sheet")
    if audit_sheet is not None:
        _append_output_target_node_for_sheet(nodes, node_ids, sheet=audit_sheet, kind="audit_sheet")

    _append_output_target_edges_for_direct_targets(edges, edge_keys, node_ids, targets=targets)
    _append_output_target_edges_for_derived_targets(edges, edge_keys, node_ids, targets=derived_targets)

    snapshot["nodes"] = _sort_nodes(nodes)
    snapshot["edges"] = _sort_edges(edges)

    return snapshot


class VizObserver(VizObserverNodeMixin, VizObserverOutputMixin, VizObserverHandlerMixin, EventDispatchObserver):
    """可视化事件观察者."""

    config: VizObserverConfig
    snapshot: Optional[Dict[str, Any]]
    run_id: Optional[str]
    _events_emitter: Optional[VizEventEmitter]
    _trace_emitter: Optional[VizEventEmitter]
    _known_node_ids: Optional[Set[str]]
    _node_id_cache: Optional[Dict[str, str]]
    _snapshot_written: bool
    _run_dir_applied: bool

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
        self._attach_viz_metadata()

    @classmethod
    def from_plan(cls, plan: ExecutionPlan, config: VizObserverConfig, *, output_composition: Optional[Any] = None) -> "VizObserver":
        snapshot = plan.to_viz_graph_snapshot()
        if output_composition is not None:
            snapshot = augment_viz_graph_snapshot_for_output_composition(snapshot, output_composition=output_composition)
        return cls(config=config, snapshot=snapshot)


__all__ = [
    "VizEventEmitter",
    "VizObserver",
    "VizObserverConfig",
]
