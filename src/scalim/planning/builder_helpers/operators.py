from typing import List, Optional, Sequence, Set, Tuple, Union

from ...spec.ir.demand import DemandIr
from ...spec.ir.fields import DerivedFieldIr, FieldIr
from ...spec.ir.sources import MainSourceIr, SourceIr
from ..operators import (
    ComputeOperatorIr,
    LoadOperatorIr,
    LoadRefOperatorIr,
    OperatorType,
    PlanOperatorIr,
)
from .resolver import LookupStepsResolver

LoaderSequenceItem = Tuple[SourceIr, List[str]]
LoaderSequence = List[LoaderSequenceItem]

RefLoaderOrderingDep = Union[str, Tuple[str, ...]]
RefLoaderField = Tuple[str, RefLoaderOrderingDep]
RefLoaderSequenceItem = Tuple[SourceIr, List[RefLoaderField]]
RefLoaderSequence = List[RefLoaderSequenceItem]


def _get_main_source(demand: DemandIr) -> Optional[MainSourceIr]:
    # `DemandIr.main_source` 在规范语义中是必填字段;但测试/不完整 IR 可能会临时设为 `None`.
    return demand.main_source


def build_plan_operators(
    *,
    demand: DemandIr,
    resolver: LookupStepsResolver,
    required_fields: Set[str],
    field_order: Sequence[str],
    loader_sequence: LoaderSequence,
    ref_loader_sequence: RefLoaderSequence,
    pre_ref_derived: Optional[Set[str]] = None,
) -> Tuple[PlanOperatorIr, ...]:
    operators: List[PlanOperatorIr] = []
    op_id = 0

    op_id = _append_load_operators(demand=demand, operators=operators, loader_sequence=loader_sequence, op_id=op_id)
    if pre_ref_derived is None:
        pre_ref_derived = derive_pre_ref_derived_field_keys(demand=demand, field_order=field_order, pre_ref_available=None)
    op_id = _append_compute_operators(
        demand=demand,
        operators=operators,
        field_order=field_order,
        required_fields=required_fields,
        op_id=op_id,
        include_field_keys=pre_ref_derived,
        exclude_field_keys=None,
    )
    op_id = _append_ref_load_operators(
        demand=demand,
        resolver=resolver,
        operators=operators,
        ref_loader_sequence=ref_loader_sequence,
        op_id=op_id,
    )
    op_id = _append_compute_operators(
        demand=demand,
        operators=operators,
        field_order=field_order,
        required_fields=required_fields,
        op_id=op_id,
        include_field_keys=None,
        exclude_field_keys=pre_ref_derived,
    )

    return tuple(operators)


def derive_pre_ref_available_field_keys(*, demand: DemandIr) -> Set[str]:
    """推导在 `LoadRef` 之前可用的主表字段集合.

    说明:
    - 当前实现仅覆盖 `main_source` 上的非 `ref` 源字段(无需 `LoadRef` 即可获得).
    - 用途: 约束当 `relation` 的连接键引用派生字段时,其依赖必须全部可在 `LoadRef` 前获得.
    """

    main_source = _get_main_source(demand)
    if main_source is None:
        return set()
    main_source_id = str(main_source.source_id or "")
    if not main_source_id:
        return set()

    available: Set[str] = set()
    for field_key, field_spec in demand.fields.items():
        if not isinstance(field_spec, FieldIr):
            continue
        source_id = str(field_spec.source.source_id or "")
        if source_id != main_source_id:
            continue
        if field_spec.lookup_steps or field_spec.relation:
            continue
        available.add(str(field_key))
    return available


def derive_pre_ref_derived_field_keys(
    *,
    demand: DemandIr,
    field_order: Sequence[str],
    pre_ref_available: Optional[Set[str]],
) -> Set[str]:
    """推导可在 `LoadRef` 之前计算的派生字段集合(`pre-ref derived`)."""

    if pre_ref_available is None:
        pre_ref_available = derive_pre_ref_available_field_keys(demand=demand)

    pre_ref_derived: Set[str] = set()
    for field_key in field_order:
        field_spec = demand.fields.get(field_key)
        if not isinstance(field_spec, DerivedFieldIr):
            continue
        if field_spec.is_constant_compute:
            pre_ref_derived.add(str(field_key))
            continue
        deps = tuple(field_spec.dependencies or ())
        if all((dep in pre_ref_available or dep in pre_ref_derived) for dep in deps):
            pre_ref_derived.add(str(field_key))
    return pre_ref_derived


def _append_load_operators(
    *,
    demand: DemandIr,
    operators: List[PlanOperatorIr],
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
                operator_id="load_{}".format(op_id),
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
    operators: List[PlanOperatorIr],
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
                    operator_id="load_ref_{}".format(op_id),
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
    operators: List[PlanOperatorIr],
    field_order: Sequence[str],
    required_fields: Set[str],
    op_id: int,
    include_field_keys: Optional[Set[str]],
    exclude_field_keys: Optional[Set[str]],
) -> int:
    for field_key in field_order:
        if field_key not in required_fields:
            continue
        field_spec = demand.fields.get(field_key)
        if isinstance(field_spec, DerivedFieldIr):
            if include_field_keys is not None and field_key not in include_field_keys:
                continue
            if exclude_field_keys is not None and field_key in exclude_field_keys:
                continue
            operators.append(
                ComputeOperatorIr(
                    operator_id="compute_{}".format(op_id),
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
    "derive_pre_ref_available_field_keys",
    "derive_pre_ref_derived_field_keys",
]
