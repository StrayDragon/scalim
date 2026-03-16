import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # notebooks/marimo: Examples & Teaching Hub

        本目录包含两层入口(同源,但用途不同):

        1) **Marimo notebooks(教学/交互入口)**：逐章讲解与可视化查看结果
        2) **Headless runner(回归入口)**：`just examples` / CI 只跑确定性对拍，不依赖 Marimo UI

        目录约定(前缀即意图):
        - `demo_*`: 端到端主线 demo（覆盖更多组合 cov，必须 deterministic）
        - `example_*`: 稳定 public surface 的最小可运行示例（小数据、快回归）
        - `tutor_*`: 长篇教学 notebook（默认不纳入 gate；如要纳入必须 deterministic 且小数据）
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Gate / 回归入口

        - `just examples`（推荐）
        - 或直接运行：`python notebooks/marimo/run_examples.py`
        - 覆盖报告(SSOT, generated)：`notebooks/marimo/marimo_coverage.gen.md`
          - 生成/校验：`just gen-marimo-coverage` / `just marimo-coverage-drift-check`
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Suites

        - `demo_big_data_report/`
          - hub: `notebooks/marimo/demo_big_data_report/demo_main.py`
          - chapters: `notebooks/marimo/demo_big_data_report/chapters/*.py`
        - `example_public_api/`
          - chapters: `notebooks/marimo/example_public_api/*.py`
        """
    )
    return


if __name__ == "__main__":
    app.run()
