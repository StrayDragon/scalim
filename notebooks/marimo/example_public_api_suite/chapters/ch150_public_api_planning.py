import marimo

from typing import Any, Dict

from scalim import planning as api
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch150_public_api_planning"


def run_public_api_planning() -> ExampleResult:
    symbols = {name: getattr(api, name) for name in api.__all__}
    demand_ir = build_minimal_public_api_ir()
    plan = api.PlanBuilder(demand_ir).build(targets=["value_plus_one"])

    passed = bool(plan.target_fields == ["value_plus_one"] and plan.field_order and plan.field_order[-1] == "value_plus_one")
    summary = "targets={} field_order={}".format(plan.target_fields, ",".join(plan.field_order))
    details: Dict[str, Any] = {
        "field_order": plan.field_order,
        "stages": plan.stages,
        "metadata": plan.metadata,
        "symbols_count": len(symbols),
    }
    return ExampleResult(
        example_id=_EXAMPLE_ID,
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_planning()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch150_public_api_planning

        本章目标:
        - 最小可运行示例: `PlanBuilder.build(...)` 的闭环

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch150_public_api_planning.py::run_public_api_planning`

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
    result = run_public_api_planning()
    chapter_result = {"passed": chapter_result["passed"], "summary": chapter_result["summary"], "details": chapter_result["details"] if chapter_result["details"] is not None else {}}
    return (chapter_result,)


@app.cell(hide_code=True)
def _(mo, chapter_result):
    mo.callout(mo.md("## {}".format("PASS" if chapter_result["passed"] else "FAIL")), kind="success" if chapter_result["passed"] else "danger")
    mo.md("```\n{}\n```".format(chapter_result["summary"]))
    return


@app.cell(hide_code=True)
def _(mo, chapter_result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
