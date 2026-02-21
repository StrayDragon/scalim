from typing import TYPE_CHECKING

from ...spec.ir.fields import FieldIr
from ...spec.ir.sources import SourceIr
from .deps import build_ref_field_ordering_deps
from .sorting import sort_ref_loaders


def build_loader_sequences(
    demand: "DemandIr",
    required_fields: set[str],
) -> tuple[list[tuple[SourceIr, list[str]]], list[tuple[SourceIr, list[tuple[str, str | tuple[str, ...]]]]]]:
    normal_loaders: dict[str, list[str]] = {}
    ref_loaders: dict[str, list[tuple[str, str | tuple[str, ...]]]] = {}
    source_map: dict[str, SourceIr] = {}
    main_source_id = demand.main_source.source_id if demand.main_source else ""

    for field_key in required_fields:
        field = demand.fields.get(field_key)
        if not isinstance(field, FieldIr):
            continue
        if field.source.source_id == main_source_id:
            continue
        if not isinstance(field.source, SourceIr):
            continue

        source_name = field.source.source_id
        source_map[source_name] = field.source

        if field.is_primary:
            normal_loaders.setdefault(source_name, []).append(field_key)
            continue

        if field.lookup_steps or field.relation:
            ref_loaders.setdefault(source_name, []).append((field_key, build_ref_field_ordering_deps(demand, field_key, field)))
            continue

        normal_loaders.setdefault(source_name, []).append(field_key)

    loader_sequence = [(source_map[name], sorted(normal_loaders[name])) for name in sorted(normal_loaders)]
    ref_loader_sequence = [(source_map[name], sorted(ref_loaders[name], key=lambda item: item[0])) for name in sorted(ref_loaders)]
    ref_loader_sequence = sort_ref_loaders(ref_loader_sequence)

    return loader_sequence, ref_loader_sequence


if TYPE_CHECKING:
    from ...spec.ir.demand import DemandIr


__all__ = [
    "build_loader_sequences",
]
