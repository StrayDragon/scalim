from typing import Any, Dict, FrozenSet, List, Optional, Set

from ....ob.presets.viz import VizObserver, VizObserverConfig
from ....planning.builder import PlanBuilder
from ..config_parsing.errors import ConfigValidationError
from ..config_parsing.loader import YamlDemandLoader
from ..schema_dsl.models import DemandConfig
from .compiler import compile  # noqa: A004
from .contracts import RunOptions

_AGG_FUNC_KEYS = ("count", "sum", "min", "max", "count_true", "count_true_gte", "count_distinct")
_RANK_FUNC_KEYS = ("row_number", "rank", "dense_rank")


def _default_output_fields_from_primary_output(config: DemandConfig) -> List[str]:
    outputs = config.outputs
    if not outputs:
        return []

    primary = outputs[0]
    aggregate = primary.aggregate
    if aggregate is None:
        if not primary.fields:
            return []
        return list(primary.fields)

    metric_ids = sorted([fid for fid, cfg in aggregate.fields.items() if str(cfg.producer_key) in _AGG_FUNC_KEYS])
    rank_ids = sorted([fid for fid, cfg in aggregate.fields.items() if str(cfg.producer_key) in _RANK_FUNC_KEYS])
    post_ids = sorted([fid for fid, cfg in aggregate.fields.items() if str(cfg.producer_key) in ("score_by_rank", "call_by")])
    return list(aggregate.group_by) + metric_ids + rank_ids + post_ids


def resolve_required_field_ids(  # noqa: C901
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

    if output_fields is not None:
        targets = list(output_fields)
    elif compilation.request.output_composition is not None:
        # 启用 `YAML` `outputs` 时,单输出的 `export_layout` 会被忽略且可能为空;默认用需求字段全集.
        targets = list(compilation.demand_ir.fields.keys())
    else:
        targets = list(compilation.request.export_layout.field_ids)
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

    if output_fields is not None:
        targets = list(output_fields)
    elif compilation.request.output_composition is not None:
        targets = list(compilation.demand_ir.fields.keys())
    else:
        targets = list(compilation.request.export_layout.field_ids)
    plan = PlanBuilder(compilation.demand_ir).build(targets=targets)

    actual_config = config or VizObserverConfig()
    return VizObserver.from_plan(plan, actual_config, output_composition=compilation.request.output_composition)


def load_output_config(yaml_path: str) -> Dict[str, Any]:
    loader = YamlDemandLoader()
    try:
        config = loader.load(yaml_path)
    except ConfigValidationError:
        raise
    except ValueError as exc:
        msg = str(exc)
        raise ConfigValidationError(msg, errors=[msg]) from exc

    params = config.main_source.params
    output_fields = _default_output_fields_from_primary_output(config)

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
        "outputs": [
            {
                "name": str(t.name),
                "from": str(t.from_) if t.from_ else None,
                "where": str(t.where) if t.where else None,
                "requires": list(t.requires or ()),
                "fields": list(t.fields) if t.fields is not None else None,
                "aggregate": (
                    None
                    if t.aggregate is None
                    else {
                        "group_by": list(t.aggregate.group_by),
                        "metric_ids": sorted([fid for fid, cfg in t.aggregate.fields.items() if str(cfg.producer_key) in _AGG_FUNC_KEYS]),
                        "rank_field_ids": sorted(
                            [fid for fid, cfg in t.aggregate.fields.items() if str(cfg.producer_key) in _RANK_FUNC_KEYS]
                        ),
                        "post_field_ids": sorted(
                            [fid for fid, cfg in t.aggregate.fields.items() if str(cfg.producer_key) in ("score_by_rank", "call_by")]
                        ),
                    }
                ),
                "container": (
                    None
                    if t.container is None
                    else {
                        "type": str(t.container.type),
                        "path": str(t.container.path),
                        "sheet": str(t.container.sheet) if t.container.sheet else None,
                    }
                ),
            }
            for t in (config.outputs or ())
        ],
    }


__all__ = [
    "build_viz_observer",
    "load_output_config",
    "resolve_required_field_ids",
]
