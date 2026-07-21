import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


def run_chapter():
    from scalim_misc.examples._types import ExampleResult
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    from notebooks.marimo.example_hooks_events_scenarios.support.post_export_upload import run_post_export_upload

    result: ExampleResult = run_post_export_upload()
    return result


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch010_post_export_upload

        演示：**导出物完成后上传到本地 HTTP mock server**。

        - Observer 订 `EventType.OUTPUT_TARGET_END`（payload 含 `output_path` / `row_count`）
        - **Demand**: `DemandRunRuntimeOptions.components=[UploadOnOutputEnd]`
        - **Workflow**: 同一 Observer 类挂在 `demand.runtime.components`；另用 `workflow_components` 订 `WORKFLOW_NODE_END` 对照编排层

        注意:
        - `OUTPUT_TARGET_END` 在 Observer 目录内，不在 Hook typed dispatch 中——上传副作用用 Observer
        - `WORKFLOW_STARTED`/`FINISHED` 当前仅在启用 workflow viz 时发出；无 viz 时用 `WORKFLOW_NODE_*`
        - SSOT: `support/post_export_upload.py`（notebook cell 在注入 repo path 后再 import）

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
    from notebooks.marimo.example_hooks_events_scenarios.support.post_export_upload import run_post_export_upload

    result = run_post_export_upload()
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
