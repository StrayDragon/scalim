from __future__ import annotations

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryRowSink

from .._types import EXAMPLE_KIND_ORACLE, ExampleResult
from ._fixtures import build_minimal_public_api_ir


def run_public_api_execution() -> ExampleResult:
    """覆盖 `scalim.execution.__all__` 的最小示例: ScalimEngine 创建/运行/最小 sink."""
    demand_ir = build_minimal_public_api_ir()
    plan = PlanBuilder(demand_ir).build()
    engine = ScalimEngine(demand=demand_ir, plan=plan, batch_size=10, parallel_mode="seq")

    sink = InMemoryRowSink()
    _ = engine.run(sink=sink)
    rows = sink.get_data()
    expected_rows = 3
    expected_first_value = 2
    passed = bool(len(rows) == expected_rows and rows[0].get("value_plus_one") == expected_first_value)
    summary = "rows={}".format(len(rows))
    return ExampleResult(
        example_id="public_api/execution",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details={"first_row": rows[0] if rows else None},
    )
