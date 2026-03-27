from typing import (
    TYPE_CHECKING,
    List,
    Sequence,
    Set,
    Tuple,
    Union,
)

from ..spec.ir import DerivedFieldIr, FieldIr, SourceIr
from .plan import PlanMetadata


def build_metadata(
    demand: "DemandIr",
    required_fields: Set[str],
    loader_sequence: Sequence[Tuple[SourceIr, List[str]]],
    ref_loader_sequence: Sequence[Tuple[SourceIr, List[Tuple[str, Union[str, Tuple[str, ...]]]]]],
    *,
    max_depth: int,
) -> PlanMetadata:
    """构建计划元数据."""
    total_fields = len(demand.fields)
    pruned_fields = total_fields - len(required_fields)

    has_derived = any(isinstance(demand.fields.get(k), DerivedFieldIr) for k in required_fields)
    has_ref = False
    for k in required_fields:
        field = demand.fields.get(k)
        if isinstance(field, FieldIr) and field.is_ref_field():
            has_ref = True
            break

    sources_used: Set[str] = set()
    for field_key in required_fields:
        field = demand.fields.get(field_key)
        if isinstance(field, FieldIr):
            sources_used.add(field.source.source_id)

    cached_sources: List[str] = []
    for source in demand.sources.values():
        if source.is_preload_forever():
            cached_sources.append(source.source_id)

    total_loaders = len(loader_sequence) + len(ref_loader_sequence)

    return PlanMetadata(
        total_fields=total_fields,
        total_sources=len(sources_used),
        total_loaders=total_loaders,
        pruned_fields=pruned_fields,
        max_depth=max_depth,
        has_derived_fields=has_derived,
        has_ref_fields=has_ref,
        cached_sources=cached_sources,
    )


if TYPE_CHECKING:
    from ..spec.ir import DemandIr

__all__ = []
