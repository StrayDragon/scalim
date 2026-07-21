import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


def run_chapter():
    from scalim_misc.examples._types import ExampleResult
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    from notebooks.marimo.example_hooks_events_scenarios.support.workflow_viz_finished import run_workflow_viz_finished

    result: ExampleResult = run_workflow_viz_finished()
    return result


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch050_workflow_viz_finished

        演示：**启用 workflow viz 后，`workflow_components` 可收到 `WORKFLOW_STARTED` / `WORKFLOW_FINISHED`**。

        - `RunOverrides(..., viz_config=VizObserverConfig(output_dir=...))`
        - Observer 挂在 `WorkflowRunOptions.workflow_components`
        - SSOT: `support/workflow_viz_finished.py`

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
    from notebooks.marimo.example_hooks_events_scenarios.support.workflow_viz_finished import run_workflow_viz_finished

    result = run_workflow_viz_finished()
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
