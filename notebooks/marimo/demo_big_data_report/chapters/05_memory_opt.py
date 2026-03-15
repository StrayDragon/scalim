import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / memory_opt

        本章目标:
        - 演示内存/写出相关优化路径的最小回归入口

        SSOT:
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/memory_opt.py::run_memory_optimization`

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
    from scalim_misc.demo_big_data_report.chapters.memory_opt import run_memory_optimization

    cfg = build_test_config_small()
    result = run_memory_optimization(cfg, batch_size=10, write_delay=0.0)
    return cfg, result, run_memory_optimization


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
