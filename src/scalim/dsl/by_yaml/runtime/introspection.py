from typing import Any, Dict, FrozenSet, List, Optional, Set

from ....ob.presets.viz import VizObserver, VizObserverConfig
from ....planning.builder import PlanBuilder
from ..config_parsing.loader import YamlDemandLoader
from .compiler import compile  # noqa: A004
from .contracts import RunOptions


def resolve_required_field_ids(
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    output_fields: Optional[List[str]] = None,
) -> List[str]:
    options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
    )
    compilation = compile(yaml_path, options=options)

    targets = list(output_fields) if output_fields is not None else list(compilation.request.export_layout.field_ids)
    plan = PlanBuilder(compilation.demand_ir).build(targets=targets)

    required_fields: Set[str] = set()
    visited: Set[str] = set()
    stack = list(plan.target_fields)
    while stack:
        field_key = stack.pop()
        if field_key in visited:
            continue
        visited.add(field_key)
        required_fields.add(field_key)
        deps = plan.field_dependencies.get(field_key, ())
        for dep in deps:
            if dep not in visited:
                stack.append(dep)

    main_source = compilation.demand_ir.main_source
    if main_source and main_source.order_by:
        for order_key in main_source.order_by:
            required_fields.add(order_key.field_key)

    ordered = [field_key for field_key in plan.field_order if field_key in required_fields]
    if main_source and main_source.order_by:
        for order_key in main_source.order_by:
            if order_key.field_key not in ordered:
                ordered.append(order_key.field_key)
    return ordered


def build_viz_observer(
    yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    output_fields: Optional[List[str]] = None,
    config: Optional[VizObserverConfig] = None,
) -> VizObserver:
    options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
    )
    compilation = compile(yaml_path, options=options)

    targets = list(output_fields) if output_fields is not None else list(compilation.request.export_layout.field_ids)
    plan = PlanBuilder(compilation.demand_ir).build(targets=targets)

    actual_config = config or VizObserverConfig()
    return VizObserver.from_plan(plan, actual_config)


def load_output_config(yaml_path: str) -> Dict[str, Any]:
    loader = YamlDemandLoader()
    config = loader.load(yaml_path)

    params = config.main_source.params
    output_fields: List[str] = []
    if config.output and config.output.fields:
        output_fields = list(config.output.fields)

    field_name_mapping: Dict[str, str] = {}
    for field_id, field_config in config.source_fields.items():
        if field_config.name:
            field_name_mapping[field_id] = field_config.name
    for field_id, field_config in config.derived_fields.items():
        if field_config.name:
            field_name_mapping[field_id] = field_config.name

    return {
        "params": params,
        "field_name_mapping": field_name_mapping,
        "output_fields": output_fields,
    }


__all__ = [
    "build_viz_observer",
    "load_output_config",
    "resolve_required_field_ids",
]
