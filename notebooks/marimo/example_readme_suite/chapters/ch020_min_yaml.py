"""Cells-native marimo notebook: ch020_min_yaml.

迁移对照:
  Before: 模块级 run_min_yaml_chapter() 持全部逻辑;cells 薄壳
  After:  support 零件(生成管线共享,不动) + 运行/断言在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch020_min_yaml

        最小可跑 YAML DSL（假数据闭环）。

        零件: `support/min_yaml.py::run_min_yaml`（README 生成管线共享，保持不动）
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

    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = repo_root
    return (repo_root,)


@app.cell
def _():
    from typing import Any, Dict

    from notebooks.marimo.example_readme_suite.support.min_yaml import run_min_yaml, yaml_path
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, make_chapter_result, render_checks, run_min_yaml, yaml_path


@app.cell
def _(mo, yaml_path):
    mo.md("**min_yaml_example.yaml**:\n\n```yaml\n{}\n```".format(yaml_path().read_text(encoding="utf-8")))
    return (yaml_path,)


@app.cell
def _(Any, Dict, run_min_yaml):
    summary: Dict[str, Any] = run_min_yaml()
    print("summary =", summary)
    return summary


@app.cell
def _(render_checks, summary):
    checks = {"YAML 运行 3 行": int(summary.get("rows") or 0) == 3}
    render_checks(checks)
    return checks


@app.cell
def _(checks, make_chapter_result, summary):
    passed = bool(all(checks.values()))
    chapter_result = make_chapter_result(
        passed=passed,
        summary=str(summary),
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
