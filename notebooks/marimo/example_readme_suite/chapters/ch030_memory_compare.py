"""Cells-native marimo notebook: ch030_memory_compare.

迁移对照:
  Before: 模块级 run_memory_compare_chapter() 持全部逻辑;cells 薄壳
  After:  knobs 表 + 对比运行 + 分步展示在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch030_memory_compare

        用假数据比较全量读取和 Scalim 的内存变化。

        这里的数字是每次运行前后进程 RSS 的变化，不是运行中的最高内存。

        零件: `support/compare.py::run_compare`（README 生成管线共享，保持不动）
        在仓库中可用 `just examples` 运行。
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
    _ = repo_root
    return (repo_root,)


@app.cell
def _(mo):
    from notebooks.marimo.example_readme_suite.support import knobs
    from notebooks.marimo.example_readme_suite.support.compare import run_compare
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    mo.ui.table(
        [
            {"knob": "N_ROWS", "value": knobs.N_ROWS},
            {"knob": "N_FIELDS", "value": knobs.N_FIELDS},
            {"knob": "BATCH_SIZE", "value": knobs.BATCH_SIZE},
            {"knob": "PAYLOAD_CHARS", "value": knobs.PAYLOAD_CHARS},
        ]
    )
    return knobs, make_chapter_result, render_checks, run_compare


@app.cell
def _(knobs, run_compare):
    summary = run_compare()
    naive = summary.get("naive") or {}
    scalim = summary.get("scalim") or {}
    print("naive  :", naive)
    print("scalim :", scalim)
    print("ratios :", summary.get("ratios"))
    return naive, scalim, summary


@app.cell
def _(mo, naive, scalim, summary):
    mo.ui.tabs(
        {
            "naive 基线": mo.ui.table([dict(naive, **{"kind": "naive"})], selection=None),
            "scalim 路径": mo.ui.table([dict(scalim, **{"kind": "scalim"})], selection=None),
            "knobs": mo.ui.table(summary.get("knobs"), selection=None),
        }
    )
    return


@app.cell
def _(naive, render_checks, scalim, summary):
    row_count_ok = bool(int(naive.get("rows") or 0) == int(scalim.get("rows") or -1) and int(naive.get("rows") or 0) > 0)
    checks = {
        "naive/scalim 行数一致且非空": row_count_ok,
    }
    render_checks(checks)
    _ = summary
    return checks, row_count_ok


@app.cell
def _(checks, make_chapter_result, naive, scalim, summary):
    passed = bool(all(checks.values()))
    chapter_result = make_chapter_result(
        passed=passed,
        summary=str(
            {
                "knobs": summary.get("knobs"),
                "ratios": summary.get("ratios"),
                "naive_rss_kb_delta": naive.get("rss_kb_delta"),
                "scalim_rss_kb_delta": scalim.get("rss_kb_delta"),
            }
        ),
        details=summary,
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
