from typing import Dict, List, Optional, Tuple, cast

from ..spec.ir.binding import BindingIr
from ..spec.ir.lookup_casts import LookupCastSpecIr
from .operators import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr
from .plan import ExecutionPlan


def _lookup_cast_snapshot(spec: Optional[LookupCastSpecIr]) -> Optional[Dict[str, object]]:
    if spec is None:
        return None
    payload: Dict[str, object] = {
        "name": str(getattr(spec, "name", "") or "auto"),  # pragma: allow-dynattr introspection: LookupCastSpecIr snapshot contract
    }
    sep = getattr(spec, "sep", None)  # pragma: allow-dynattr introspection: LookupCastSpecIr snapshot contract
    if sep is not None:
        payload["sep"] = str(sep)
    return payload


def _binding_snapshot(binding: Optional[BindingIr]) -> Optional[Dict[str, object]]:
    if binding is None:
        return None

    payload: Dict[str, object] = {
        "key_field": binding.key_field,
        "mode": str(binding.mode or "keys"),
        "as": str(binding.as_ or "set"),
        "cache_mode": str(binding.cache_mode or "none"),
        "param_name": str(binding.param_name or ""),
        "template_path": str(binding.template_path or ""),
    }

    template = binding.params_template
    if template is not None:
        keys = getattr(  # pragma: allow-dynattr optional-interface: params_template keys contract
            template,
            "top_level_mapping_string_keys",
            None,
        )
        if callable(keys):
            payload["template_top_level_keys"] = list(cast("Tuple[str, ...]", keys()))  # pragma: allow-cast template contract boundary

    if binding.params_builder_ref is not None:
        payload["params_builder_ref"] = str(binding.params_builder_ref)

    return payload


def _lookup_step_snapshot(step: object) -> Dict[str, object]:
    from_field = getattr(step, "from_field", None)  # pragma: allow-dynattr introspection: LookupStepIr snapshot contract
    to_source = getattr(step, "to_source", None)  # pragma: allow-dynattr introspection: LookupStepIr snapshot contract
    to_field = getattr(step, "to_field", None)  # pragma: allow-dynattr introspection: LookupStepIr snapshot contract
    lookup_cast = getattr(step, "lookup_cast", None)  # pragma: allow-dynattr introspection: LookupStepIr snapshot contract
    bind = getattr(step, "bind", None)  # pragma: allow-dynattr introspection: LookupStepIr snapshot contract

    to_source_id = getattr(to_source, "source_id", None)  # pragma: allow-dynattr introspection: source ref contract

    from_field_snapshot: object = from_field
    if isinstance(from_field, tuple):
        from_field_snapshot = list(cast("Tuple[object, ...]", from_field))  # pragma: allow-cast runtime typed narrowing

    payload: Dict[str, object] = {
        "from_field": from_field_snapshot,
        "to_source_id": str(to_source_id or ""),
    }
    if to_field is not None:
        to_field_snapshot: object = to_field
        if isinstance(to_field, tuple):
            to_field_snapshot = list(cast("Tuple[object, ...]", to_field))  # pragma: allow-cast runtime typed narrowing
        payload["to_field"] = to_field_snapshot
    cast_snapshot = _lookup_cast_snapshot(lookup_cast if isinstance(lookup_cast, LookupCastSpecIr) else None)
    if cast_snapshot is not None:
        payload["lookup_cast"] = cast_snapshot
    bind_snapshot = _binding_snapshot(bind if isinstance(bind, BindingIr) else None)
    if bind_snapshot is not None:
        payload["bind"] = bind_snapshot
    return payload


def operator_snapshot(op: object) -> Dict[str, object]:
    if isinstance(op, LoadOperatorIr):
        return {
            "operator_id": str(op.operator_id),
            "operator_type": str(op.operator_type),
            "source_id": str(op.source_id),
            "field_keys": list(op.field_keys),
            "depends_on": list(op.depends_on),
            "is_primary": bool(op.is_primary),
        }
    if isinstance(op, ComputeOperatorIr):
        return {
            "operator_id": str(op.operator_id),
            "operator_type": str(op.operator_type),
            "field_key": str(op.field_key),
            "input_fields": list(op.input_fields),
            "depends_on": list(op.depends_on),
        }
    if isinstance(op, LoadRefOperatorIr):
        return {
            "operator_id": str(op.operator_id),
            "operator_type": str(op.operator_type),
            "source_id": str(op.source_id),
            "field_key": str(op.field_key),
            "lookup_steps": [_lookup_step_snapshot(step) for step in (op.lookup_steps or ())],
            "depends_on": list(op.depends_on),
            "use_cache": bool(op.use_cache),
        }
    msg = "Unsupported operator type: {}".format(type(op).__name__)
    raise TypeError(msg)


def execution_plan_snapshot(plan: ExecutionPlan, *, schema_version: str = "execution_plan/v1") -> Dict[str, object]:
    return {
        "schema_version": str(schema_version),
        "operators": [operator_snapshot(op) for op in (plan.operators or ())],
        "field_order": list(plan.field_order or []),
        "target_fields": list(plan.target_fields or []),
        "primary_field": plan.primary_field,
        "key_fields": sorted(plan.key_fields or frozenset()),
    }


def execution_deps_snapshot(plan: ExecutionPlan, *, schema_version: str = "execution_deps/v1") -> Dict[str, object]:
    deps = plan.field_dependencies or {}

    edges: List[Tuple[str, str]] = []
    for field_key in deps:
        for dep in deps.get(field_key) or ():
            edges.append((str(dep), str(field_key)))
    edges.sort()

    dependencies_by_field = {str(k): list(deps.get(k) or ()) for k in (plan.field_order or list(deps))}

    return {
        "schema_version": str(schema_version),
        "edges": [{"from": a, "to": b} for a, b in edges],
        "dependencies_by_field": dependencies_by_field,
    }


__all__ = (
    "execution_deps_snapshot",
    "execution_plan_snapshot",
    "operator_snapshot",
)
