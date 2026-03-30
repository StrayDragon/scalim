"""PlanBuilder high-level contract tests.

These tests focus on `PlanBuilder.build()` observable outputs and error contracts.
They intentionally avoid asserting on internal helper/cache behavior.
"""

import pytest

from scalim.planning import PlanBuilder
from scalim.planning.operators import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr, OperatorType

from tests.fixtures.planning_fixtures import build_derived_model, build_relation_model, build_simple_model


def test_build_defaults_to_all_fields() -> None:
    demand = build_simple_model()
    plan = PlanBuilder(demand).build()

    assert set(plan.target_fields) == {"order_id", "amount", "cost"}


def test_build_rejects_unknown_targets() -> None:
    demand = build_simple_model()

    with pytest.raises(ValueError, match="不存在"):
        PlanBuilder(demand).build(targets=["nonexistent_field"])


@pytest.mark.parametrize(
    ("demand_builder", "targets"),
    [
        (build_derived_model, ["order_id", "profit"]),
        (build_relation_model, ["order_id", "customer_name"]),
    ],
    ids=["derived", "relation"],
)
def test_build_operators_are_core_types(demand_builder, targets) -> None:  # type: ignore[no-untyped-def]
    core_types = {
        OperatorType.LOAD.value,
        OperatorType.LOAD_REF.value,
        OperatorType.COMPUTE.value,
    }

    plan = PlanBuilder(demand_builder()).build(targets=targets)

    assert plan.operators
    assert {op.operator_type for op in plan.operators} <= core_types
    assert all(isinstance(op, (LoadOperatorIr, LoadRefOperatorIr, ComputeOperatorIr)) for op in plan.operators)


def test_build_simple_plan_excludes_main_source_from_loader_sequence() -> None:
    demand = build_simple_model()
    plan = PlanBuilder(demand).build(targets=["order_id", "amount"])

    assert plan.loader_sequence == []
