"""Cells-native marimo notebook: ch150_public_api_planning.

迁移对照:
  Before: 模块级 run_public_api_planning() 持全部逻辑;cells 薄壳
  After:  symbols 触达 / 复杂零件装配窥视 / PlanBuilder 闭环在 cells 内
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
        2. 复杂可复用零件：`build_minimal_public_api_ir()` 装配最小 `DemandIr`
           （主源 `items` + `item_id`/`dim_id` 抽取字段 + 派生字段 `value_plus_one`）
        3. `PlanBuilder(demand_ir).build(targets=[...])`
        4. **模型窥视**：渲染 `demand_ir.fields` 结构与 `plan.metadata`（读者无需跳库）
        5. 断言：target_fields / field_order
        6. 汇总 chapter_result

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
    # ① 触达 public __all__ + 复杂可复用零件装配 + PlanBuilder 闭环。
    #   - build_minimal_public_api_ir(): 复用库 fixtures 构造最小 DemandIr
    #     （主源 items + item_id/dim_id 抽取字段 + value_plus_one 派生字段）。
    #   - PlanBuilder(demand_ir).build(targets=[...]): 依据 demand IR 与目标字段裁剪出执行计划。
    symbols = {name: getattr(api, name) for name in api.__all__}
    demand_ir = build_minimal_public_api_ir()
    plan = api.PlanBuilder(demand_ir).build(targets=["value_plus_one"])

    print("targets     =", plan.target_fields)
    print("field_order =", plan.field_order)
    print("symbols     =", len(symbols))
    return demand_ir, plan, symbols


@app.cell(hide_code=True)
def _(demand_ir, mo, plan):
    # ② 模型窥视：把库 fixtures builder 的装配产物直接渲染在 notebook 内，读者无需跳库。
    #   - demand_ir.fields 是 mappingproxy（键=field_id），必须用 .values() 遍历；
    #     DerivedFieldIr 可能没有 source_id，用 getattr 兜底。
    #   - plan.metadata 暴露 total_sources / total_fields 元数据。
    fields_summary = [
        {
            "field_id": f.field_id,
            "name": f.name,
            "source_id": getattr(f, "source_id", "-"),
            "kind": type(f).__name__,
        }
        for f in demand_ir.fields.values()
    ]
    meta = plan.metadata
    mo.vstack(
        [
            mo.md("**模型窥视（读者无需跳库）**——以下为 `build_minimal_public_api_ir` 的装配产物："),
            mo.md(
                "字段总数 `{}`（含派生 {} 个）；`plan.metadata`: total_sources={} total_fields={}；targets = {}".format(
                    len(fields_summary),
                    sum(1 for f in fields_summary if f["kind"] == "DerivedFieldIr"),
                    meta.total_sources,
                    meta.total_fields,
                    plan.target_fields,
                )
            ),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return


@app.cell
def _(plan, render_checks):
    # ③ 断言展开
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
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"target_fields": ["value_plus_one"], "field_order_last": "value_plus_one"}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
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
