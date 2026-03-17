import marimo

from typing import Any, Dict

from scalim_misc.examples.public_api._coverage import (
    check_public_all_coverage,
    coverage_failure_summary,
    coverage_to_details,
)
from scalim import execution as api
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir

__generated_with = "0.20.2"
app = marimo.App(width="full")

_COVERED_PUBLIC_ALL = {
    "ScalimEngine",
}


def run_public_api_execution() -> ExampleResult:
    coverage = check_public_all_coverage(api, covered=_COVERED_PUBLIC_ALL)
    if not coverage.ok:
        return ExampleResult(
            example_id="demo_big_data_report/ch160_public_api_execution",
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary=coverage_failure_summary(coverage),
            details=coverage_to_details(coverage),
        )

    symbols = {name: getattr(api, name) for name in api.__all__}
    demand_ir = build_minimal_public_api_ir()
    plan = PlanBuilder(demand_ir).build()
    engine = api.ScalimEngine(demand=demand_ir, plan=plan, batch_size=10, parallel_mode="seq")

    sink = InMemoryRowSink()
    _ = engine.run(sink=sink)
    rows = sink.get_data()

    passed = bool(len(rows) == 3 and rows and rows[0].get("value_plus_one") == 2)
    summary = "rows={}".format(len(rows))
    details: Dict[str, Any] = {"first_row": rows[0] if rows else None, "symbols_count": len(symbols)}
    return ExampleResult(
        example_id="demo_big_data_report/ch160_public_api_execution",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_execution()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch160_public_api_execution

        本章目标:
        - 覆盖 `scalim.execution.__all__` 的最小可运行示例
        - 演示 `ScalimEngine` 创建/运行/内存 sink

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/ch160_public_api_execution.py::run_public_api_execution`

        Gate:
        - `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_public_api_execution()
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
