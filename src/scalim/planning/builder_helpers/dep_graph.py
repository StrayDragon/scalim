from typing import Dict, Sequence, Tuple

from ...spec.ir.demand import DemandIr
from ...spec.ir.fields import DerivedFieldIr, FieldIr
from ...utils import graph
from .resolver import LookupStepsResolver, extract_relation_dependency_keys


def build_dependency_graph(
    *,
    demand: DemandIr,
    resolver: LookupStepsResolver,
) -> "graph.DependencyGraph[str]":
    """为给定的 `DemandIr` 构建规划依赖图."""
    dep_graph: graph.DependencyGraph[str] = graph.DependencyGraph()

    for field_key, field in demand.fields.items():
        if isinstance(field, DerivedFieldIr):
            dep_graph.add_node(field_key, field.dependencies)
            continue
        if isinstance(field, FieldIr):
            if field.lookup_steps or field.relation:
                deps = extract_relation_dependency_keys(demand=demand, field_spec=field, resolver=resolver, field_key=field_key)
                dep_graph.add_node(field_key, deps)
            else:
                dep_graph.add_node(field_key)
            continue

        dep_graph.add_node(field_key)

    return dep_graph


def build_field_dependencies(
    *,
    field_order: Sequence[str],
    dep_graph: "graph.DependencyGraph[str]",
) -> Dict[str, Tuple[str, ...]]:
    """根据依赖图构建字段依赖映射."""
    field_dependencies: Dict[str, Tuple[str, ...]] = {}
    for field_key in field_order:
        field_dependencies[field_key] = tuple(dep_graph.get_deps(field_key))
    return field_dependencies


__all__ = [
    "build_dependency_graph",
    "build_field_dependencies",
]
