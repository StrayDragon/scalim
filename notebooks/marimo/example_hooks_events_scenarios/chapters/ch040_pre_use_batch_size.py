import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


def run_chapter():
    from scalim_misc.examples._types import ExampleResult
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    from notebooks.marimo.example_hooks_events_scenarios.support.pre_use_batch_size import run_pre_use_batch_size

    result: ExampleResult = run_pre_use_batch_size()
    return result


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch040_pre_use_batch_size

        演示：**Hook 在 `pre_use_batch_size` 策略信号里改写 batch_size**。

        - 仅当 `DemandRunRuntimeOptions.batch_size` 为 `UNSET` 时才会发射信号
        - Hook: `decision.override(2, reason=...)`
        - Observer 订 `PIPELINE_START` 核对生效后的 `batch_size`
        - SSOT: `support/pre_use_batch_size.py`

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
    from notebooks.marimo.example_hooks_events_scenarios.support.pre_use_batch_size import run_pre_use_batch_size

    result = run_pre_use_batch_size()
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
