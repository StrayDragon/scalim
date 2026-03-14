from __future__ import annotations

from scalim.planning import PlanBuilder

from .._types import EXAMPLE_KIND_ORACLE, ExampleResult
from ._fixtures import build_minimal_public_api_ir


def run_public_api_planning() -> ExampleResult:
    """覆盖 `scalim.planning.__all__` 的最小示例: PlanBuilder.build + 可观察输出断言."""
    demand_ir = build_minimal_public_api_ir()
    plan = PlanBuilder(demand_ir).build(targets=["value_plus_one"])
    passed = bool(plan.target_fields == ["value_plus_one"] and plan.field_order[-1] == "value_plus_one")
    summary = "targets={} field_order={}".format(plan.target_fields, ",".join(plan.field_order))
    return ExampleResult(
        example_id="public_api/planning",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details={"field_order": plan.field_order, "stages": plan.stages, "metadata": plan.metadata},
    )
