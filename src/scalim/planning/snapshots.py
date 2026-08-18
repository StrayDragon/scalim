from typing import Any, Dict, List, Optional, Tuple, cast

from ..spec.ir._relations import LookupStepIr
from ..spec.ir.binding import BindingIr
from ..spec.ir.lookup_casts import LookupCastSpecIr
from ..typedefs import RuntimeValue
from ..vendor.compact.typing_extensionsx import Protocol, runtime_checkable
from .operators import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr
from .plan import ExecutionPlan


@runtime_checkable
class _SupportsTopLevelMappingStringKeys(Protocol):
    def top_level_mapping_string_keys(self) -> Tuple[str, ...]: ...


def _lookup_cast_snapshot(spec: Optional[LookupCastSpecIr]) -> Optional[Dict[str, Any]]:
    if spec is None:
        return None
    payload: Dict[str, Any] = {
        "name": str(spec.name or "auto"),
    }
    if spec.sep is not None:
        payload["sep"] = str(spec.sep)
    return payload


def _binding_snapshot(binding: Optional[BindingIr]) -> Optional[Dict[str, Any]]:
    if binding is None:
        return None

    payload: Dict[str, Any] = {
        "key_field": binding.key_field,
        "mode": str(binding.mode or "keys"),
        "as": str(binding.as_ or "set"),
        "cache_mode": str(binding.cache_mode or "none"),
        "param_name": str(binding.param_name or ""),
        "template_path": str(binding.template_path or ""),
    }

    template = binding.params_template
    if isinstance(template, _SupportsTopLevelMappingStringKeys):
        keys = template.top_level_mapping_string_keys
        if callable(keys):
            payload["template_top_level_keys"] = list(keys())

    if binding.params_builder_ref is not None:
        payload["params_builder_ref"] = str(binding.params_builder_ref)

    return payload


def _lookup_step_snapshot(step: LookupStepIr) -> Dict[str, Any]:
    from_field = step.from_field
    to_field = step.to_field
    lookup_cast = step.lookup_cast
    bind = step.bind

    to_source_id = step.to_source_id

    from_field_snapshot: Any = from_field
    if isinstance(from_field, tuple):
        from_field_snapshot = list(cast("Tuple[RuntimeValue, ...]", from_field))  # pragma: allow-cast runtime typed narrowing

    payload: Dict[str, Any] = {
        "from_field": from_field_snapshot,
        "to_source_id": str(to_source_id or ""),
    }
    if to_field is not None:
        to_field_snapshot: Any = to_field
        if isinstance(to_field, tuple):
            to_field_snapshot = list(cast("Tuple[RuntimeValue, ...]", to_field))  # pragma: allow-cast runtime typed narrowing
        payload["to_field"] = to_field_snapshot
    cast_snapshot = _lookup_cast_snapshot(lookup_cast)
    if cast_snapshot is not None:
        payload["lookup_cast"] = cast_snapshot
    bind_snapshot = _binding_snapshot(bind)
    if bind_snapshot is not None:
        payload["bind"] = bind_snapshot
    return payload


def operator_snapshot(op: RuntimeValue) -> Dict[str, Any]:
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


def execution_plan_snapshot(plan: ExecutionPlan, *, schema_version: str = "execution_plan/v1") -> Dict[str, Any]:
    return {
        "schema_version": str(schema_version),
        "operators": [operator_snapshot(op) for op in (plan.operators or ())],
        "field_order": list(plan.field_order or []),
        "target_fields": list(plan.target_fields or []),
        "primary_field": plan.primary_field,
        "key_fields": sorted(plan.key_fields or frozenset()),
    }


def execution_deps_snapshot(plan: ExecutionPlan, *, schema_version: str = "execution_deps/v1") -> Dict[str, Any]:
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
