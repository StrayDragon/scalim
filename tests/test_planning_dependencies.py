import pytest

from scalim.planning.builder import PlanBuilder
from scalim.utils.graph import CyclicDependencyError
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr

from .fixtures.planning_fixtures import (
    build_derived_model,
    build_multi_field_model,
    build_multi_level_model,
    build_relation_model,
    make_main_source,
    make_source,
)


@pytest.mark.parametrize(
    ("demand_builder", "targets", "must_include", "must_exclude"),
    [
        (build_derived_model, ["profit"], ("amount", "cost", "profit"), ()),
        (build_relation_model, ["customer_name"], ("customer_id", "customer_name"), ()),
        (build_multi_level_model, ["country_name"], ("pay_id", "country_id", "country_name"), ()),
        (build_multi_field_model, ["mapping_name"], ("region_id", "institution_id", "mapping_name"), ()),
        (build_derived_model, ["order_id"], ("order_id",), ("profit",)),
    ],
    ids=["derived", "relation", "multi-level", "multi-field", "prune-derived"],
)
def test_build_collects_required_fields(demand_builder, targets, must_include, must_exclude) -> None:  # type: ignore[no-untyped-def]
    plan = PlanBuilder(demand_builder()).build(targets=targets)

    for field_key in must_include:
        assert field_key in plan.field_order
    for field_key in must_exclude:
        assert field_key not in plan.field_order


@pytest.mark.parametrize(
    ("demand_builder", "targets", "after", "before"),
    [
        (build_derived_model, ["profit"], "profit", ("amount", "cost")),
        (build_relation_model, ["customer_name"], "customer_name", ("customer_id",)),
    ],
    ids=["derived", "relation"],
)
def test_field_order_places_dependencies_before_dependents(demand_builder, targets, after, before) -> None:  # type: ignore[no-untyped-def]
    plan = PlanBuilder(demand_builder()).build(targets=targets)

    after_idx = plan.field_order.index(after)
    for before_key in before:
        assert after_idx > plan.field_order.index(before_key)


def test_cyclic_dependency_raises() -> None:
    source = make_main_source("test")

    fields = [
        FieldIr(field_id="id", name="ID", source=source, is_primary=True),
        DerivedFieldIr(field_id="a", name="A", dependencies=("b",), calculator=lambda b: b),
        DerivedFieldIr(field_id="b", name="B", dependencies=("a",), calculator=lambda a: a),
    ]

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=source)

    with pytest.raises(CyclicDependencyError):
        PlanBuilder(demand).build(targets=["a"])


def test_relation_without_main_source_dependencies() -> None:
    main_source = make_main_source("orders")
    left_source = make_source("left", key_field="left_id")
    right_source = make_source("right", key_field="right_id")

    relation = left_source["left_id"].join(right_source["right_id"])
    demand = DemandIr.from_irs(
        sources=[left_source, right_source],
        fields=[FieldIr(field_id="left_id", name="Left", source=left_source, relation=relation)],
        main_source=main_source,
    )

    plan = PlanBuilder(demand).build(targets=["left_id"])
    assert plan.field_dependencies["left_id"] == ()
