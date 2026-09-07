"""Cells-native marimo notebook: ch150_public_api_planning.

迁移对照:
  Before: 模块级 run_public_api_planning() 持全部逻辑;cells 薄壳
  After:  symbols 触达 / PlanBuilder 闭环在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch150_public_api_planning

        本章目标:
        - 最小可运行示例: `PlanBuilder.build(...)` 的闭环

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 触达 `scalim.planning` 的 public `__all__`
        2. `PlanBuilder(demand_ir).build(targets=[...])`
        3. 断言：target_fields / field_order
        4. 汇总 chapter_result

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
    from typing import Any, Dict

    from scalim import planning as api
    from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, api, build_minimal_public_api_ir, make_chapter_result, render_checks


@app.cell
def _(api, build_minimal_public_api_ir):
    # 触达 public __all__ + PlanBuilder 闭环
    symbols = {name: getattr(api, name) for name in api.__all__}
    demand_ir = build_minimal_public_api_ir()
    plan = api.PlanBuilder(demand_ir).build(targets=["value_plus_one"])

    print("targets     =", plan.target_fields)
    print("field_order =", plan.field_order)
    print("symbols     =", len(symbols))
    return demand_ir, plan, symbols


@app.cell
def _(plan, render_checks):
    checks = {
        "target_fields == [value_plus_one]": plan.target_fields == ["value_plus_one"],
        "field_order 末位为 value_plus_one": bool(plan.field_order) and plan.field_order[-1] == "value_plus_one",
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, make_chapter_result, plan, symbols):
    passed = bool(all(checks.values()))
    summary = "targets={} field_order={}".format(plan.target_fields, ",".join(plan.field_order))
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "field_order": plan.field_order,
            "stages": plan.stages,
            "metadata": plan.metadata,
            "symbols_count": len(symbols),
            "checks": {k: bool(v) for k, v in checks.items()},
        },
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
