from typing import FrozenSet, Set

from ...spec.ir import DemandIr, FieldIr
from .resolver import LookupStepsResolver


def compute_key_fields(
    *,
    demand: DemandIr,
    resolver: LookupStepsResolver,
    required_fields: Set[str],
) -> FrozenSet[str]:
    """计算关键字段(来自 `lookup_steps` 的信号)."""
    key_fields: Set[str] = set()

    main_source = demand.main_source
    if main_source:
        for field_key in required_fields:
            field = demand.fields.get(field_key)
            if isinstance(field, FieldIr):
                steps = resolver.resolve(
                    field,
                    main_source,
                    field_key=field_key,
                    to_source=demand.sources.get(field.source_id),
                )
                if steps:
                    for step in steps:
                        key_fields.update(step.get_from_fields())

    return frozenset(key_fields)


__all__ = ("compute_key_fields",)
