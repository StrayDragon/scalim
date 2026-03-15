import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / output_composition

        本章目标:
        - 演示 composed outputs(workbook) 的端到端写出与对拍口径

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/output_composition.py::run_output_composition`

        Gate:
        - `just examples`（跑全量）
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import tempfile
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return Path, tempfile


@app.cell
def _(Path, tempfile):
    from scalim_misc.demo_big_data_report.chapters.output_composition import run_output_composition

    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_output_composition(Path(tmpdir))
    return result, run_output_composition


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
