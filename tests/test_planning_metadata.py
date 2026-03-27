from scalim.planning import PlanBuilder
from scalim.spec.ir import DemandIr
from scalim.spec.ir import DerivedFieldIr, FieldIr

from .fixtures.planning_fixtures import build_derived_model, build_multi_level_model, build_relation_model, make_main_source


def test_metadata_fields_count() -> None:
    demand = build_derived_model()
    plan = PlanBuilder(demand).build(targets=["profit"])

    assert plan.metadata.total_fields == 4  # order_id, amount, cost, profit
    assert plan.metadata.has_derived_fields is True


def test_metadata_pruned_count() -> None:
    demand = build_derived_model()
    plan = PlanBuilder(demand).build(targets=["order_id"])

    assert plan.metadata.pruned_fields >= 1


def test_metadata_has_ref_fields() -> None:
    demand = build_relation_model()
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    assert plan.metadata.has_ref_fields is True


def test_metadata_max_depth_multi_level_relation() -> None:
    demand = build_multi_level_model()
    plan = PlanBuilder(demand).build(targets=["country_name"])

    assert plan.metadata.max_depth == 1


def test_metadata_max_depth_multi_layer_derived_dependencies() -> None:
    source = make_main_source("orders")

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=source, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=source),
        DerivedFieldIr(field_id="inc", name="Inc", dependencies=("amount",), calculator=lambda amount: (amount or 0) + 1),
        DerivedFieldIr(field_id="double_inc", name="DoubleInc", dependencies=("inc",), calculator=lambda inc: (inc or 0) * 2),
    ]

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=source)
    plan = PlanBuilder(demand).build(targets=["double_inc"])

    assert plan.metadata.max_depth == 2
