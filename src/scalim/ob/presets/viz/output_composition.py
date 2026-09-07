from collections.abc import Iterable
from typing import Any, Protocol, cast


class _OutputSpecLike(Protocol):
    path: Any
    sheet_name: Any


class _ExportLayoutLike(Protocol):
    field_ids: Iterable[str]


class _OutputTargetNodeLike(Protocol):
    target_id: Any
    output: _OutputSpecLike | None
    is_primary: bool


class _OutputTargetDirectLike(_OutputTargetNodeLike, Protocol):
    layout: _ExportLayoutLike | None
    requires: tuple[str, ...] | None


class _DerivedSpecLike(Protocol):
    def required_fields(self) -> Iterable[str]: ...


class _OutputTargetDerivedLike(_OutputTargetNodeLike, Protocol):
    derived: _DerivedSpecLike | None
    requires: tuple[str, ...] | None


class _OutputSheetLike(Protocol):
    target_id: Any
    output: _OutputSpecLike | None
    sheet_name: Any


class _OutputCompositionLike(Protocol):
    targets: Iterable[_OutputTargetDirectLike]
    derived_targets: Iterable[_OutputTargetDerivedLike]
    meta_sheet: _OutputSheetLike | None
    audit_sheet: _OutputSheetLike | None


def _get_snapshot_node_ids(snapshot: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    nodes_value = snapshot.get("nodes")
    if not isinstance(nodes_value, list):
        return ids
    nodes = cast("list[dict[str, Any]]", nodes_value)  # pragma: allow-cast snapshot nodes typed narrowing
    for item in nodes:
        node_id = item.get("id")
        if node_id:
            ids.add(str(node_id))
    return ids


def _ensure_snapshot_list(snapshot: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = snapshot.get(key)
    if isinstance(value, list):
        return cast("list[dict[str, Any]]", value)  # pragma: allow-cast snapshot list typed narrowing
    out: list[dict[str, Any]] = []
    snapshot[key] = out
    return out


def _get_snapshot_edge_keys(edges: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        edge_type = str(edge.get("type") or "")
        if source and target and edge_type:
            keys.add((source, target, edge_type))
    return keys


def _as_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return text


def _describe_output_spec(output: _OutputSpecLike | None) -> tuple[str | None, str | None]:
    if output is None:
        return None, None
    output_path = _as_optional_text(output.path)
    sheet_name = _as_optional_text(output.sheet_name)
    return output_path, sheet_name


def _append_output_target_nodes_for_targets(
    nodes: list[dict[str, Any]],
    node_ids: set[str],
    *,
    targets: Iterable[_OutputTargetNodeLike],
    kind: str,
) -> None:
    for target in targets:
        target_id = _as_optional_text(target.target_id)
        if not target_id:
            continue
        output_path, sheet_name = _describe_output_spec(target.output)
        _add_output_target_node(
            nodes,
            node_ids,
            target_id=target_id,
            kind=kind,
            output_path=output_path,
            sheet_name=sheet_name,
            is_primary=bool(target.is_primary),
        )


def _append_output_target_node_for_sheet(
    nodes: list[dict[str, Any]],
    node_ids: set[str],
    *,
    sheet: _OutputSheetLike,
    kind: str,
) -> None:
    target_id = _as_optional_text(sheet.target_id)
    if not target_id:
        return
    output_path, _sheet_name = _describe_output_spec(sheet.output)
    sheet_name = _as_optional_text(sheet.sheet_name)
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
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    node_ids: set[str],
    *,
    targets: Iterable[_OutputTargetDirectLike],
) -> None:
    for target in targets:
        target_id = _as_optional_text(target.target_id)
        if not target_id:
            continue
        layout = target.layout
        if layout is None:
            continue
        try:
            field_ids = layout.field_ids
        except AttributeError:
            continue
        requires = target.requires
        for field_id in _iter_unique_field_ids(field_ids, requires):
            _maybe_add_output_target_edge(edges, edge_keys, node_ids, source_field_id=field_id, target_id=target_id)


def _append_output_target_edges_for_derived_targets(
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    node_ids: set[str],
    *,
    targets: Iterable[_OutputTargetDerivedLike],
) -> None:
    for target in targets:
        target_id = _as_optional_text(target.target_id)
        if not target_id:
            continue
        derived = target.derived
        if derived is None:
            continue
        try:
            required_fields = derived.required_fields
        except AttributeError:
            continue
        if not callable(required_fields):
            continue
        required_fields = required_fields()
        requires = target.requires
        for field_id in _iter_unique_field_ids(required_fields, requires):
            _maybe_add_output_target_edge(edges, edge_keys, node_ids, source_field_id=field_id, target_id=target_id)


def _sort_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(nodes, key=lambda item: str(item.get("id", "")))


def _sort_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def edge_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(item.get("source", "")),
            str(item.get("target", "")),
            str(item.get("type", "")),
            str(item.get("id", "")),
        )

    return sorted(edges, key=edge_key)


def _add_output_target_node(
    nodes: list[dict[str, Any]],
    node_ids: set[str],
    *,
    target_id: str,
    kind: str,
    output_path: str | None,
    sheet_name: str | None,
    is_primary: bool,
) -> None:
    node_id = f"output_target:{target_id}"
    if node_id in node_ids:
        return
    node_ids.add(node_id)
    data: dict[str, Any] = {
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


def _iter_unique_field_ids(field_ids: Iterable[str], requires: tuple[str, ...] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in list(field_ids) + list(requires or ()):
        key = str(item)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return tuple(ordered)


def _maybe_add_output_target_edge(
    edges: list[dict[str, Any]],
    edge_keys: set[tuple[str, str, str]],
    node_ids: set[str],
    *,
    source_field_id: str,
    target_id: str,
) -> None:
    source = f"field:{source_field_id}"
    target = f"output_target:{target_id}"
    edge_type = "composed_from"
    if source not in node_ids or target not in node_ids:
        return
    key = (source, target, edge_type)
    if key in edge_keys:
        return
    edge_keys.add(key)
    edges.append(
        {
            "id": f"e_out:{source}:{target}:{edge_type}",
            "source": source,
            "target": target,
            "type": edge_type,
            "data": {"type": edge_type},
        }
    )


def augment_viz_graph_snapshot_for_output_composition(
    snapshot: dict[str, Any],
    *,
    output_composition: _OutputCompositionLike,
) -> dict[str, Any]:
    """对 `VizGraphSnapshot` 做最小增强:追加 `output_target:*` 节点与 `composed_from` 边."""

    if not snapshot or not isinstance(snapshot, dict):
        return snapshot

    nodes = _ensure_snapshot_list(snapshot, "nodes")
    edges = _ensure_snapshot_list(snapshot, "edges")

    node_ids = _get_snapshot_node_ids(snapshot)
    edge_keys = _get_snapshot_edge_keys(edges)

    targets = output_composition.targets
    derived_targets = output_composition.derived_targets
    meta_sheet = output_composition.meta_sheet
    audit_sheet = output_composition.audit_sheet

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


__all__ = ("augment_viz_graph_snapshot_for_output_composition",)
