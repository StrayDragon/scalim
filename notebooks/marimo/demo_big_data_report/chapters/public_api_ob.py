import marimo

from typing import Any, Dict

from scalim_misc.examples.public_api._coverage import (
    check_public_all_coverage,
    coverage_failure_summary,
    coverage_to_details,
)
from scalim.events.catalog import EVENT_PIPELINE_END, EVENT_PIPELINE_START
from scalim import ob as api
from scalim_misc.examples._types import EXAMPLE_KIND_SMOKE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_COVERED_PUBLIC_ALL = {
    "Observability",
}


def run_public_api_ob() -> ExampleResult:
    coverage = check_public_all_coverage(api, covered=_COVERED_PUBLIC_ALL)
    if not coverage.ok:
        return ExampleResult(
            example_id="demo_big_data_report/public_api_ob",
            passed=False,
            kind=EXAMPLE_KIND_SMOKE,
            summary=coverage_failure_summary(coverage),
            details=coverage_to_details(coverage),
        )

    symbols = {name: getattr(api, name) for name in api.__all__}
    ob = api.Observability()
    manager = ob.build_manager(mode="capture")
    manager.emit_pipeline_start(targets=["item_id"], batch_size=2)
    manager.emit_pipeline_end(total_batches=1, total_duration=0.01)

    events = manager.drain_events()
    passed = bool([e.event_type for e in events] == [EVENT_PIPELINE_START, EVENT_PIPELINE_END])
    summary = "events={} types={}".format(len(events), ",".join(e.event_type for e in events))
    details: Dict[str, Any] = {"event_types": [e.event_type for e in events], "symbols_count": len(symbols)}
    return ExampleResult(
        example_id="demo_big_data_report/public_api_ob",
        passed=passed,
        kind=EXAMPLE_KIND_SMOKE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_ob()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / public_api_ob

        本章目标:
        - 覆盖 `scalim.ob.__all__` 的最小可运行示例
        - 演示 capture manager + 事件序列断言

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/public_api_ob.py::run_public_api_ob`

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
    result = run_public_api_ob()
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
