import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / observability

        本章目标:
        - 演示 observability 相关路径的最小回归入口

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/observability.py::run_observability`

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
    from scalim_misc.demo_big_data_report.chapters.observability import run_observability
    from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL

    cfg = build_test_config_small()
    targets = TARGET_FIELDS_FULL[:12]
    result = run_observability(cfg, targets=targets, batch_size=10)
    return TARGET_FIELDS_FULL, cfg, result, run_observability, targets


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
