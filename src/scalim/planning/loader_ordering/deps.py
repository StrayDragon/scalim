import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

from ...spec.ir.fields import FieldIr
from ...spec.ir.helpers import extract_from_fields, infer_lookup_steps
from ...spec.ir.sources import SourceIr

_logger = logging.getLogger(__name__)


def build_ref_field_ordering_deps(demand: "DemandIr", field_key: str, field: FieldIr) -> tuple[str, ...]:
    """Build dependency signals for ordering ref fields.

    Returns a tuple of **field keys** derived from lookup steps `from_field` that
    can be mapped back to other ref loaders. This is planning-time ordering
    signal (not runtime `lookup_keys`).
    """
    steps = field.lookup_steps
    if steps is None and field.relation and demand.main_source and isinstance(field.source, SourceIr):
        steps = infer_lookup_steps(field.relation, demand.main_source, field.source)

    if not steps:
        return ()

    main_source_id = demand.main_source.source_id if demand.main_source else ""
    raw_deps = extract_from_fields(steps)

    deps: list[str] = []
    for dep_key in raw_deps:
        if dep_key == field_key:
            continue
        dep_field = demand.fields.get(dep_key)
        if not isinstance(dep_field, FieldIr):
            continue
        if dep_field.source.source_id == main_source_id:
            continue
        if not isinstance(dep_field.source, SourceIr):
            continue
        if not (dep_field.lookup_steps or dep_field.relation):
            continue
        deps.append(dep_key)

    # Deduplicate while preserving order (Py3.6+ dict order is insertion order).
    return tuple(OrderedDict.fromkeys(deps))


if TYPE_CHECKING:
    from ...spec.ir.demand import DemandIr


__all__ = [
    "build_ref_field_ordering_deps",
]
