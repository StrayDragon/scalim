from typing import FrozenSet, Optional, Tuple, Union

from ..spec.ir.aliases import LookupKeySpec, NormalizedLookupKeySpec
from ..spec.ir.binding import BindingIr
from ..spec.ir.relations import LookupStepIr
from ..typedefs import LookupKey
from .converters import NamedLookupCast, auto_normalize_key

LookupCastSignature = Tuple[str, Union[str, int]]
BindingParamMarker = Union[str, int]
BindingSignature = Tuple[str, str, str, str, NormalizedLookupKeySpec, BindingParamMarker]
StepSignature = Tuple[str, Tuple[str, ...], NormalizedLookupKeySpec, Optional[LookupCastSignature], Optional[BindingSignature]]
RelationSignature = Tuple[StepSignature, ...]
LoadRefCacheKey = Tuple[StepSignature, FrozenSet[LookupKey]]


def is_auto_lookup_cast(lookup_cast: object) -> bool:
    if lookup_cast is auto_normalize_key:
        return True
    if isinstance(lookup_cast, NamedLookupCast) and lookup_cast.scalim_lookup_cast_name == "auto":
        return True
    # 兼容历史的私有标记字段.
    return getattr(lookup_cast, "_scalim_lookup_cast_name", None) == "auto"  # pragma: allow-dynattr legacy: lookup_cast marker


def normalize_key_field(key_field: LookupKeySpec) -> NormalizedLookupKeySpec:
    if isinstance(key_field, list):
        return tuple(key_field)
    if isinstance(key_field, tuple):
        return key_field
    return key_field


def lookup_cast_signature(lookup_cast: Optional[object]) -> Optional[LookupCastSignature]:
    if lookup_cast is None:
        return None
    if lookup_cast is auto_normalize_key:
        return ("auto", "auto_normalize_key")
    if isinstance(lookup_cast, NamedLookupCast):
        return ("named", lookup_cast.scalim_lookup_cast_name)
    return ("callable", id(lookup_cast))


def build_binding_signature(binding: Optional[BindingIr]) -> Optional[BindingSignature]:
    if binding is None:
        return None
    param_marker = binding.param_name if binding.param_name is not None else id(binding.params_builder)
    return ("binding", binding.mode, binding.as_, binding.cache_mode, binding.key_field, param_marker)


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
    lookup_cast_sig = lookup_cast_signature(step.lookup_cast)
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


__all__ = [
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
]
