import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / basics

        本章目标:
        - 走一遍最小主线：`IR → Plan → Engine → Sink`
        - 对拍(oracle)失败时可在本 notebook 里交互定位

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/basics.py::run_basics`

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
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _():
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.chapters.basics import run_basics
    from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL

    cfg = build_test_config_small()
    result = run_basics(cfg, targets=TARGET_FIELDS_FULL, batch_size=10)
    return TARGET_FIELDS_FULL, cfg, result, run_basics


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
