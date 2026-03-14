from __future__ import annotations

from scalim.execution.run_ir import ExecutionRequest, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim.sinks.sink_memory import InMemoryRowSink

from .._types import EXAMPLE_KIND_ORACLE, ExampleResult
from ._fixtures import build_minimal_public_api_ir


def run_public_api_spec_ir() -> ExampleResult:
    """覆盖 `scalim.spec.ir.__all__` 的最小示例: 构造 IR + 走一条可运行的执行链路."""
    demand_ir = build_minimal_public_api_ir()
    export_layout = export_layout_from_demand_ir(demand_ir, ("item_id", "dim_id", "value_plus_one"), header_fields_output_by="field_id")
    sink = InMemoryRowSink()
    request = ExecutionRequest(
        export_layout=export_layout,
        output=OutputSpec(path=None),
        sink=sink,
        output_composition=None,
        observability=None,
        guardrails=None,
        loader_retry=None,
        components=None,
        batch_size=10,
        parallel_mode="seq",
        max_workers=0,
    )
    core = run_ir(demand_ir, request)
    rows = sink.get_data()
    expected_rows = 3
    expected_first_value = 2
    passed = bool(core.total_rows == len(rows) == expected_rows and rows[0]["value_plus_one"] == expected_first_value)
    summary = "rows={} total_rows={}".format(len(rows), core.total_rows)
    return ExampleResult(
        example_id="public_api/spec_ir",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details={"rows": rows},
    )
