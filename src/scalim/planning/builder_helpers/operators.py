from collections.abc import Sequence

from ...spec.ir.demand import DemandIr
from ...spec.ir.fields import DerivedFieldIr, FieldIr
from ...spec.ir.sources import SourceIr
from ..operators import (
    ComputeOperatorIr,
    LoadOperatorIr,
    LoadRefOperatorIr,
    OperatorType,
    PlanOperatorIr,
)
from .resolver import LookupStepsResolver

LoaderSequenceItem = tuple[SourceIr, list[str]]
LoaderSequence = list[LoaderSequenceItem]

RefLoaderOrderingDep = str | tuple[str, ...]
RefLoaderField = tuple[str, RefLoaderOrderingDep]
RefLoaderSequenceItem = tuple[SourceIr, list[RefLoaderField]]
RefLoaderSequence = list[RefLoaderSequenceItem]


def build_plan_operators(
    *,
    demand: DemandIr,
    resolver: LookupStepsResolver,
    required_fields: set[str],
    field_order: Sequence[str],
    loader_sequence: LoaderSequence,
    ref_loader_sequence: RefLoaderSequence,
) -> tuple[PlanOperatorIr, ...]:
    operators: list[PlanOperatorIr] = []
    op_id = 0

    op_id = _append_load_operators(demand=demand, operators=operators, loader_sequence=loader_sequence, op_id=op_id)
    op_id = _append_ref_load_operators(
        demand=demand,
        resolver=resolver,
        operators=operators,
        ref_loader_sequence=ref_loader_sequence,
        op_id=op_id,
    )
    op_id = _append_compute_operators(
        demand=demand, operators=operators, field_order=field_order, required_fields=required_fields, op_id=op_id
    )

    return tuple(operators)


def _append_load_operators(
    *,
    demand: DemandIr,
    operators: list[PlanOperatorIr],
    loader_sequence: LoaderSequence,
    op_id: int,
) -> int:
    for source, field_keys in loader_sequence:
        is_primary = False
        for field_key in field_keys:
            field = demand.fields.get(field_key)
            if isinstance(field, FieldIr) and field.is_primary:
                is_primary = True
                break

        operators.append(
            LoadOperatorIr(
                operator_id=f"load_{op_id}",
                operator_type=OperatorType.LOAD.value,
                source=source,
                field_keys=tuple(field_keys),
                is_primary=is_primary,
            )
        )
        op_id += 1
    return op_id


def _append_ref_load_operators(
    *,
    demand: DemandIr,
    resolver: LookupStepsResolver,
    operators: list[PlanOperatorIr],
    ref_loader_sequence: RefLoaderSequence,
    op_id: int,
) -> int:
    for source, ref_fields in ref_loader_sequence:
        for field_key, _ in ref_fields:
            field_spec = demand.fields.get(field_key)
            if not isinstance(field_spec, FieldIr) or not (field_spec.lookup_steps or field_spec.relation):
                continue

            main_source = demand.main_source
            if not main_source:
                continue

            if not isinstance(field_spec.source, SourceIr):
                continue

            steps = resolver.resolve(field_spec, main_source, field_key=field_key)
            if not steps:
                continue

            operators.append(
                LoadRefOperatorIr(
                    operator_id=f"load_ref_{op_id}",
                    operator_type=OperatorType.LOAD_REF.value,
                    source=source,
                    field_key=field_key,
                    field_spec=field_spec,
                    lookup_steps=steps,
                    use_cache=source.is_preload_forever(),
                )
            )
            op_id += 1
    return op_id


def _append_compute_operators(
    *,
    demand: DemandIr,
    operators: list[PlanOperatorIr],
    field_order: Sequence[str],
    required_fields: set[str],
    op_id: int,
) -> int:
    for field_key in field_order:
        if field_key not in required_fields:
            continue
        field_spec = demand.fields.get(field_key)
        if isinstance(field_spec, DerivedFieldIr):
            operators.append(
                ComputeOperatorIr(
                    operator_id=f"compute_{op_id}",
                    operator_type=OperatorType.COMPUTE.value,
                    field_spec=field_spec,
                    input_fields=field_spec.dependencies,
                )
            )
            op_id += 1
    return op_id


__all__ = [
    "LoaderSequence",
    "LoaderSequenceItem",
    "RefLoaderField",
    "RefLoaderOrderingDep",
    "RefLoaderSequence",
    "RefLoaderSequenceItem",
    "build_plan_operators",
]
