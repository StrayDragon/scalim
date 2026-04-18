import marimo

from typing import Any, Dict

from scalim import execution as api
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryRowDataSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir, build_minimal_public_api_runtime_bindings

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch160_public_api_execution"


def run_public_api_execution() -> ExampleResult:
    symbols = {name: getattr(api, name) for name in api.__all__}
    demand_ir = build_minimal_public_api_ir()
    runtime_bindings = build_minimal_public_api_runtime_bindings()
    plan = PlanBuilder(demand_ir).build()

    sink = InMemoryRowDataSink()
    request = api.ExecutionRequest(
        export_layout=api.export_layout_from_demand_ir(demand_ir, plan.target_fields),
        output=api.OutputSpec(path=None),
        sink=sink,
        runtime_bindings=runtime_bindings,
        batch_size=10,
        parallel_mode="seq",
    )
    _ = api.run_ir(demand_ir, request)
    rows = sink.get_data()

    passed = bool(len(rows) == 3 and rows and rows[0].get("value_plus_one") == 2)
    summary = "rows={}".format(len(rows))
    details: Dict[str, Any] = {"first_row": rows[0] if rows else None, "symbols_count": len(symbols)}
    return ExampleResult(
        example_id=_EXAMPLE_ID,
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
        # example_public_api_suite / ch160_public_api_execution

        本章目标:
        - 最小可运行示例: execution facade(`run_ir` + `ExecutionRequest`)运行 + 内存 sink

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch160_public_api_execution.py::run_public_api_execution`

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
