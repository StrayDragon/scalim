import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Scalim 公共入口示例套件: `example_public_api`

        目标:
        - 以 **稳定的 public re-export 模块** 为索引,提供“从哪导入/怎么用/关键边界是什么”的最小示例
        - 章节实现 SSOT 在 `packages/scalim-misc/src/scalim_misc/examples/public_api/`
        - `just examples` 会通过 `notebooks/marimo/run_examples.py` 统一回归
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    from scalim_misc.examples.harness import format_results, run_public_api_examples

    results = run_public_api_examples()
    lines = format_results(results)
    mo.md("```\n{}\n```".format("\n".join(lines)))
    return lines, results


if __name__ == "__main__":
    app.run()
