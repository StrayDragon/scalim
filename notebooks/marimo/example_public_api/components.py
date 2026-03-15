import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api / components (hooks + observers)

        目标:
        - 演示 `components=[Observer(), IExecutionHook()]` 的最小用法
        - 自定义 Hook/Observer 并对拍其是否生效

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/examples/public_api/components.py::run_public_api_components`

        Gate:
        - `just examples`
        - pytest: `tests/test_example_public_api_suite.py`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    from scalim_misc.examples.public_api.components import run_public_api_components

    result = run_public_api_components()
    mo.md("```\n{}\n```".format(result.summary))
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    return result


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    if rows:
        mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()

