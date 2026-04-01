# region imports

import time
from typing import Any, Dict, List, Set, Tuple, Union

from ..spec.ir import DerivedFieldIr, FieldIr, MainSourceIr, SourceIr, SupportedFieldIr
from ..vendor.dataclassesx import asdict

# endregion


def _viz_add_node(
    nodes: List[Dict[str, Any]],
    node_ids: Set[str],
    node_id: str,
    node_type: str,
    data: Dict[str, Any],
) -> None:
    if node_id in node_ids:
        return
    node_ids.add(node_id)
    nodes.append(
        {
            "id": node_id,
            "type": node_type,
            "data": data,
            # `XYFlow` 需要 `position`,这里使用占位值.
            "position": {"x": 0, "y": 0},
        }
    )


def _viz_add_edge(
    edges: List[Dict[str, Any]],
    edge_counter: List[int],
    source: str,
    target: str,
    edge_type: str,
) -> None:
    edge_id = "e{}:{}:{}:{}".format(edge_counter[0], source, target, edge_type)
    edge_counter[0] += 1
    edges.append(
        {
            "id": edge_id,
            "source": source,
            "target": target,
            "type": edge_type,
            "data": {"type": edge_type},
        }
    )


def _viz_sort_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def edge_key(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
        return (
            str(item.get("source", "")),
            str(item.get("target", "")),
            str(item.get("type", "")),
            str(item.get("id", "")),
        )

    sorted_edges = sorted(edges, key=edge_key)
    for idx, edge in enumerate(sorted_edges):
        edge["id"] = "e{}:{}:{}:{}".format(idx, edge.get("source", ""), edge.get("target", ""), edge.get("type", ""))
    return sorted_edges


def _viz_collect_fields(
    field_specs: Dict[str, SupportedFieldIr],
    add_node: Any,
) -> Tuple[Dict[str, Union[SourceIr, MainSourceIr]], Dict[str, List[str]]]:
    sources: Dict[str, Union[SourceIr, MainSourceIr]] = {}
    fields_by_source: Dict[str, List[str]] = {}
    for field_key, field_spec in field_specs.items():
        node_id = "field:{}".format(field_key)
        if isinstance(field_spec, DerivedFieldIr):
            add_node(
                node_id,
                "derived",
                {
                    "label": field_spec.name,
                    "field_key": field_key,
                    "kind": "derived",
                },
            )
            continue
        if isinstance(field_spec, FieldIr):
            source = field_spec.source
            source_id = source.source_id
            sources[source_id] = source
            fields_by_source.setdefault(source_id, []).append(field_key)
            add_node(
                node_id,
                "field",
                {
                    "label": field_spec.name,
                    "field_key": field_key,
                    "source_id": source_id,
                    "is_ref": field_spec.is_ref_field(),
                },
            )
            continue
        add_node(node_id, "field", {"label": field_key, "field_key": field_key})
    return sources, fields_by_source


def _viz_add_source_nodes(
    sources: Dict[str, Union[SourceIr, MainSourceIr]],
    add_node: Any,
) -> None:
    for source_id, source in sources.items():
        add_node(
            "source:{}".format(source_id),
            "source",
            {
                "label": source_id,
                "source_id": source_id,
                "is_main": isinstance(source, MainSourceIr),
            },
        )


def _viz_add_loader_nodes(
    sources: Dict[str, Union[SourceIr, MainSourceIr]],
    add_node: Any,
) -> None:
    for source_id in sources:
        add_node(
            "loader:{}".format(source_id),
            "loader",
            {
                "label": source_id,
                "loader_name": source_id,
            },
        )


def _viz_add_dependency_edges(
    field_dependencies: Dict[str, Tuple[str, ...]],
    add_edge: Any,
) -> None:
    for field_key, deps in field_dependencies.items():
        for dep in deps:
            add_edge("field:{}".format(dep), "field:{}".format(field_key), "depends_on")


def _viz_add_source_edges(
    fields_by_source: Dict[str, List[str]],
    field_specs: Dict[str, SupportedFieldIr],
    *,
    include_source_nodes: bool,
    include_loader_nodes: bool,
    add_edge: Any,
) -> None:
    for source_id, field_keys in fields_by_source.items():
        source_node = "source:{}".format(source_id)
        loader_node = "loader:{}".format(source_id)
        if include_loader_nodes and include_source_nodes:
            add_edge(source_node, loader_node, "loads_from")
        for field_key in field_keys:
            field_spec = field_specs.get(field_key)
            edge_type = "loads_from"
            if isinstance(field_spec, FieldIr) and field_spec.is_ref_field():
                edge_type = "ref_lookup"

            if include_loader_nodes:
                add_edge(loader_node, "field:{}".format(field_key), edge_type)
            elif include_source_nodes:
                add_edge(source_node, "field:{}".format(field_key), edge_type)


def _viz_stage_records(stages: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": stage.stage_id,
            "level": stage.level,
            "field_keys": sorted(stage.field_keys),
        }
        for stage in stages
    ]


def _viz_add_stage_nodes(stages: List[Any], add_node: Any, add_edge: Any) -> None:
    for stage in stages:
        stage_id = "stage:{}".format(stage.stage_id)
        add_node(
            stage_id,
            "stage",
            {
                "label": stage.stage_id,
                "stage_id": stage.stage_id,
                "level": stage.level,
            },
        )
        for field_key in stage.field_keys:
            add_edge(stage_id, "field:{}".format(field_key), "in_stage")


def _viz_build_meta(metadata: Any, target_fields: List[str], schema_version: str) -> Dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": time.time(),
        "target_fields": list(target_fields),
        "metadata": asdict(metadata),
    }


def build_viz_graph_snapshot(
    plan: Any,
    *,
    schema_version: str = "vizgraph/v1",
    include_stage_nodes: bool = True,
    include_loader_nodes: bool = True,
    include_source_nodes: bool = True,
) -> Dict[str, Any]:
    """生成 `VizGraphSnapshot`(用于可视化).

    返回一个字典,包含 `nodes`/`edges`/`meta`,并保证稳定的排序规则.
    """

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()
    edge_counter = [0]

    def add_node(node_id: str, node_type: str, data: Dict[str, Any]) -> None:
        _viz_add_node(nodes, node_ids, node_id, node_type, data)

    def add_edge(source: str, target: str, edge_type: str) -> None:
        _viz_add_edge(edges, edge_counter, source, target, edge_type)

    sources, fields_by_source = _viz_collect_fields(plan.field_specs, add_node)
    if include_source_nodes:
        _viz_add_source_nodes(sources, add_node)
    if include_loader_nodes:
        _viz_add_loader_nodes(sources, add_node)

    _viz_add_dependency_edges(plan.field_dependencies, add_edge)
    _viz_add_source_edges(
        fields_by_source,
        plan.field_specs,
        include_source_nodes=include_source_nodes,
        include_loader_nodes=include_loader_nodes,
        add_edge=add_edge,
    )

    stages = _viz_stage_records(plan.stages)
    if include_stage_nodes:
        _viz_add_stage_nodes(plan.stages, add_node, add_edge)

    meta = _viz_build_meta(plan.metadata, plan.target_fields, schema_version)

    return {
        "nodes": sorted(nodes, key=lambda item: item.get("id", "")),
        "edges": _viz_sort_edges(edges),
        "meta": meta,
        "stages": stages,
    }


__all__ = ("build_viz_graph_snapshot",)
