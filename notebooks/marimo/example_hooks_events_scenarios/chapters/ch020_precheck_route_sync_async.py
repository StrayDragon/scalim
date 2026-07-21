import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


def run_chapter():
    from scalim_misc.examples._types import ExampleResult
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    from notebooks.marimo.example_hooks_events_scenarios.support.precheck_route import run_precheck_route_sync_async

    result: ExampleResult = run_precheck_route_sync_async()
    return result


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch020_precheck_route_sync_async

        演示：**应用层预估完成后 HTTP 分流**（不绑 Scalim `workflow_preflight`）。

        1. `estimate_job(estimated_rows=...)` mock 预估
        2. `POST /dispatch` → `sync`（小任务）或 `async`（大任务）
        3. sync → 直接 `run` / `run_workflow`；async → 只入队 mock，不跑 Scalim

        demand 与 workflow 走同一套路由封装。SSOT: `support/precheck_route.py`

        Gate: `just examples`
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

    ensure_repo_root_on_sys_path(__file__)
    from notebooks.marimo.example_hooks_events_scenarios.support.precheck_route import run_precheck_route_sync_async

    result = run_precheck_route_sync_async()
    chapter_result = {
        "passed": chapter_result["passed"],
        "summary": chapter_result["summary"],
        "details": chapter_result["details"] if chapter_result["details"] is not None else {},
    }
    return (chapter_result,)


@app.cell(hide_code=True)
def _(mo, chapter_result):
    mo.callout(
        mo.md("## {}".format("PASS" if chapter_result["passed"] else "FAIL")), kind="success" if chapter_result["passed"] else "danger"
    )
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
