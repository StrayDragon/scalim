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
        - `just examples`/CI 会通过 `notebooks/marimo/run_examples.py` 统一回归(不依赖 Marimo UI)

        失败定位:
        - 先看本页汇总输出(章节 id + summary)
        - 再打开对应章节 notebook(同目录下的 `*.py`)
        - 或直接跑 pytest: `tests/test_example_public_api_suite.py`
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
    failed = [r for r in results if not r.passed]

    rows = []
    for r in results:
        first_line = r.summary.splitlines()[0] if r.summary else ""
        rows.append(
            {
                "example_id": r.example_id,
                "kind": r.kind,
                "passed": r.passed,
                "summary": first_line,
            }
        )

    mo.callout(
        mo.md("## {}".format("PASS" if not failed else "FAIL")),
        kind="success" if not failed else "danger",
    )
    mo.ui.table(rows, selection=None)
    mo.md("```\n{}\n```".format("\n".join(lines)))
    mo.callout(
        mo.md("提示：`just examples` 会通过 `notebooks/marimo/run_examples.py` 统一回归(不依赖 Marimo UI)。"),
        kind="info",
    )
    return failed, lines, results, rows


if __name__ == "__main__":
    app.run()
