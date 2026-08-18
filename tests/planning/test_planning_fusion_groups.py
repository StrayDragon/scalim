"""`ExecutionPlan.compute_fusion_groups` 推导契约 (c20 / r960)."""

from typing import Any, Dict, List, Tuple

from scalim.planning import PlanBuilder
from scalim.planning.builder_helpers.fusion_groups import derive_compute_fusion_groups
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, RuntimeHandleIdIr

from tests.fixtures.planning_fixtures import make_main_source


def _call_by(handle_suffix: str, dep_fields: List[str]) -> CallBySpecIr:
    return CallBySpecIr(
        reference=RuntimeHandleIdIr(handle_id="derived.{}".format(handle_suffix)),
        args=tuple(CallByValueIr(kind="field", value=dep) for dep in dep_fields),
        field_names=tuple(dep_fields),
    )


def test_identical_deps_form_one_fusion_group() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source_id=main.source_id, is_primary=True),
        FieldIr(field_id="amount", name="金额", source_id=main.source_id),
        DerivedFieldIr(field_id="d0", name="d0", dependencies=("amount",), call_by=_call_by("d0", ["amount"])),
        DerivedFieldIr(field_id="d1", name="d1", dependencies=("amount",), call_by=_call_by("d1", ["amount"])),
        DerivedFieldIr(field_id="d2", name="d2", dependencies=("amount",), call_by=_call_by("d2", ["amount"])),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "d0", "d1", "d2"])

    assert len(plan.compute_fusion_groups) == 1
    group = plan.compute_fusion_groups[0]
    assert group.field_keys == ("d0", "d1", "d2")
    assert group.deps == ("amount",)
    assert group.segment == "pre_ref"


def test_unequal_deps_not_fused() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source_id=main.source_id, is_primary=True),
        FieldIr(field_id="a", name="a", source_id=main.source_id),
        FieldIr(field_id="b", name="b", source_id=main.source_id),
        DerivedFieldIr(field_id="d0", name="d0", dependencies=("a",), call_by=_call_by("d0", ["a"])),
        DerivedFieldIr(field_id="d1", name="d1", dependencies=("a", "b"), call_by=_call_by("d1", ["a", "b"])),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=["order_id", "a", "b", "d0", "d1"])

    assert plan.compute_fusion_groups == ()


def test_ctx_call_by_excluded_from_fusion_group() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source_id=main.source_id, is_primary=True),
        FieldIr(field_id="amount", name="金额", source_id=main.source_id),
        DerivedFieldIr(field_id="d0", name="d0", dependencies=("amount",), call_by=_call_by("d0", ["amount"])),
        DerivedFieldIr(
            field_id="with_ctx",
            name="with_ctx",
            dependencies=("amount",),
            call_by=_call_by("with_ctx", ["amount"]),
            call_ctx_key="ctx",
        ),
        DerivedFieldIr(field_id="d1", name="d1", dependencies=("amount",), call_by=_call_by("d1", ["amount"])),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "d0", "with_ctx", "d1"])

    member_keys = {fk for g in plan.compute_fusion_groups for fk in g.field_keys}
    assert "with_ctx" not in member_keys


def _compute_op(field_key: str) -> ComputeOperatorIr:
    return ComputeOperatorIr(
        operator_id="compute:{}".format(field_key),
        operator_type=OperatorType.COMPUTE.value,
        field_key=field_key,
        input_fields=(),
    )


def test_non_derived_compute_member_breaks_the_group() -> None:
    main = make_main_source("orders")
    field_specs: Dict[str, Any] = {
        "amount": FieldIr(field_id="amount", name="金额", source_id=main.source_id),
        "d0": DerivedFieldIr(field_id="d0", name="d0", dependencies=("amount",), call_by=_call_by("d0", ["amount"])),
        "d1": DerivedFieldIr(field_id="d1", name="d1", dependencies=("amount",), call_by=_call_by("d1", ["amount"])),
    }
    field_dependencies: Dict[str, Tuple[str, ...]] = {"amount": (), "d0": ("amount",), "d1": ("amount",)}

    groups = derive_compute_fusion_groups(
        operators=[_compute_op("d0"), _compute_op("amount"), _compute_op("d1")],
        field_specs=field_specs,
        field_dependencies=field_dependencies,
    )

    assert groups == ()


def test_interdependent_fields_not_in_same_group() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source_id=main.source_id, is_primary=True),
        FieldIr(field_id="amount", name="金额", source_id=main.source_id),
        DerivedFieldIr(field_id="base", name="base", dependencies=("amount",), compute_expr="amount * 2"),
        DerivedFieldIr(field_id="next", name="next", dependencies=("base",), compute_expr="base + 1"),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "base", "next"])

    assert plan.compute_fusion_groups == ()
