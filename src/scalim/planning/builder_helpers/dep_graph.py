from collections.abc import Sequence

from ...spec.ir.demand import DemandIr
from ...spec.ir.fields import DerivedFieldIr
from ...utils import graph
from .resolver import LookupStepsResolver, extract_relation_dependency_keys


def build_dependency_graph(
    *,
    demand: DemandIr,
    resolver: LookupStepsResolver,
) -> "graph.DependencyGraph[str]":
    """Build planning dependency graph for the given demand."""
    dep_graph: graph.DependencyGraph[str] = graph.DependencyGraph()

    for field_key, field_spec in demand.fields.items():
        if isinstance(field_spec, DerivedFieldIr):
            dep_graph.add_node(field_key, field_spec.dependencies)
            continue

        try:
            has_relation_deps = bool(field_spec.lookup_steps or field_spec.relation)
        except AttributeError:
            dep_graph.add_node(field_key)
            continue

        if has_relation_deps:
            deps = extract_relation_dependency_keys(demand=demand, field_spec=field_spec, resolver=resolver, field_key=field_key)
            dep_graph.add_node(field_key, deps)
        else:
            dep_graph.add_node(field_key)

    return dep_graph


def build_field_dependencies(
    *,
    field_order: Sequence[str],
    dep_graph: "graph.DependencyGraph[str]",
) -> dict[str, tuple[str, ...]]:
    """Build field dependency map from the dependency graph."""
    field_dependencies: dict[str, tuple[str, ...]] = {}
    for field_key in field_order:
        field_dependencies[field_key] = tuple(dep_graph.get_deps(field_key))
    return field_dependencies


__all__ = [
    "build_dependency_graph",
    "build_field_dependencies",
]
