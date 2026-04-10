from typing import FrozenSet, Optional, Tuple

from ..spec.ir import LookupStepIr
from ..spec.ir.aliases import LookupKeySpec, NormalizedLookupKeySpec
from ..spec.ir.binding import BindingIr
from ..spec.ir.callable_refs import describe_callable_ref
from ..spec.ir.lookup_casts import LookupCastSpecIr, lookup_cast_id
from ..typedefs import LookupKey

LookupCastSignature = Tuple[str, str]
BindingParamMarker = str
BindingSignature = Tuple[str, str, str, str, NormalizedLookupKeySpec, BindingParamMarker]
StepSignature = Tuple[str, Tuple[str, ...], NormalizedLookupKeySpec, Optional[LookupCastSignature], Optional[BindingSignature]]
RelationSignature = Tuple[StepSignature, ...]
LoadRefCacheKey = Tuple[StepSignature, FrozenSet[LookupKey]]


def is_auto_lookup_cast(lookup_cast: Optional[LookupCastSpecIr]) -> bool:
    if lookup_cast is None:
        return False
    return str(lookup_cast.name or "").strip() == "auto"


def normalize_key_field(key_field: LookupKeySpec) -> NormalizedLookupKeySpec:
    if isinstance(key_field, list):
        return tuple(key_field)
    if isinstance(key_field, tuple):
        return key_field
    return key_field


def lookup_cast_signature(lookup_cast: Optional[LookupCastSpecIr], *, is_multi: bool) -> Optional[LookupCastSignature]:
    if lookup_cast is None:
        return None
    return ("spec", lookup_cast_id(lookup_cast, is_multi=is_multi))


def build_binding_signature(binding: Optional[BindingIr]) -> Optional[BindingSignature]:
    if binding is None:
        return None
    marker = ""
    if binding.params_builder_ref is not None:
        marker = "params_builder_ref:{}".format(describe_callable_ref(binding.params_builder_ref))
    elif binding.params_template is not None:
        marker = "params_template:{}".format(str(binding.template_path or "(template)"))
    else:
        marker = "params:none"
    if binding.param_name is not None:
        marker = "{}:param={!r}".format(marker, binding.param_name)
    return ("binding", binding.mode, binding.as_, binding.cache_mode, binding.key_field, marker)


def resolve_step_binding(step: LookupStepIr) -> Optional[BindingIr]:
    to_key = step.get_to_key_or_source_key()
    binding_key = normalize_key_field(to_key)
    return step.bind or step.to_source.get_binding(binding_key)


def has_rows_binding(steps: Tuple[LookupStepIr, ...]) -> bool:
    for step in steps:
        binding = resolve_step_binding(step)
        if binding is None:
            continue
        if binding.mode != "keys":
            return True
    return False


def can_group_by_relation(steps: Tuple[LookupStepIr, ...]) -> bool:
    for step in steps:
        binding = resolve_step_binding(step)
        if binding is None:
            continue
        if binding.mode == "rows" and binding.cache_mode == "none":
            return False
    return True


def build_step_signature(step: LookupStepIr) -> StepSignature:
    to_key = normalize_key_field(step.get_to_key_or_source_key())
    effective_cast = step.lookup_cast if step.lookup_cast is not None else step.to_source.key.cast
    lookup_cast_sig = lookup_cast_signature(effective_cast, is_multi=step.is_multi_field())
    binding_signature = build_binding_signature(resolve_step_binding(step))
    return (
        step.to_source.source_id,
        step.get_from_fields(),
        to_key,
        lookup_cast_sig,
        binding_signature,
    )


def build_relation_signature(steps: Tuple[LookupStepIr, ...]) -> RelationSignature:
    return tuple(build_step_signature(step) for step in steps)


__all__ = (
    "LoadRefCacheKey",
    "LookupCastSignature",
    "RelationSignature",
    "StepSignature",
    "build_binding_signature",
    "build_relation_signature",
    "build_step_signature",
    "can_group_by_relation",
    "has_rows_binding",
    "is_auto_lookup_cast",
    "lookup_cast_signature",
    "normalize_key_field",
    "resolve_step_binding",
)
