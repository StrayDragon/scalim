"""Cells-native marimo notebook: ch160_public_api_execution.

迁移对照:
  Before: 模块级 run_public_api_execution() 持全部逻辑;cells 薄壳
  After:  复杂零件装配窥视 / execution facade 闭环在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / chapters_of_ir / ch160_public_api_execution

        本章目标:
        - 最小可运行示例: execution facade(`run_ir` + `ExecutionRequest`)运行 + 内存 sink

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 触达 `scalim.execution` 的 public `__all__`
        2. 复杂可复用零件：`build_minimal_public_api_ir()` + `build_minimal_public_api_runtime_bindings()`
        3. **模型窥视**：渲染 `demand_ir.fields` 与 `runtime_bindings` 接线（读者无需跳库）
        4. PlanBuilder → ExecutionRequest（内存 sink）→ `run_ir`
        5. 断言：行数 + value_plus_one == 2
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

    from scalim import execution as api
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryRowDataSink
    from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir, build_minimal_public_api_runtime_bindings
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        Dict,
        PlanBuilder,
        InMemoryRowDataSink,
        api,
        build_minimal_public_api_ir,
        build_minimal_public_api_runtime_bindings,
        make_chapter_result,
        render_checks,
    )


@app.cell
def _(PlanBuilder, api, build_minimal_public_api_ir, build_minimal_public_api_runtime_bindings):
    # ① 触达 public __all__ + 复杂可复用零件装配。
    #   - build_minimal_public_api_ir(): 最小 DemandIr（主源 items + 2 抽取字段 + 1 派生字段）。
    #   - build_minimal_public_api_runtime_bindings(): 把主源 loader 与派生计算函数注入 RuntimeBindings。
    #   - PlanBuilder(demand_ir).build(): 依据 demand IR 生成执行计划。
    symbols = {name: getattr(api, name) for name in api.__all__}
    demand_ir = build_minimal_public_api_ir()
    runtime_bindings = build_minimal_public_api_runtime_bindings()
    plan = PlanBuilder(demand_ir).build()
    print("targets =", plan.target_fields)
    return demand_ir, plan, runtime_bindings, symbols


@app.cell(hide_code=True)
def _(demand_ir, mo, plan, runtime_bindings):
    # ② 模型窥视：把库 fixtures builder 的装配产物直接渲染在 notebook 内，读者无需跳库。
    #   - demand_ir.fields 是 mappingproxy（键=field_id），必须用 .values() 遍历；
    #     DerivedFieldIr 可能没有 source_id，用 getattr 兜底。
    #   - runtime_bindings.main_source_loaders / derived_calculators 是运行期注入点。
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
            mo.md("**模型窥视（读者无需跳库）**——以下为最小模型的装配与接线产物："),
            mo.md(
                "字段总数 `{}`（含派生 {} 个）；`plan.metadata`: total_sources={} total_fields={}；"
                "source_loaders = {}；derived_calculators = {}".format(
                    len(fields_summary),
                    sum(1 for f in fields_summary if f["kind"] == "DerivedFieldIr"),
                    meta.total_sources,
                    meta.total_fields,
                    list(getattr(runtime_bindings, "main_source_loaders", {}).keys()),
                    list(getattr(runtime_bindings, "derived_calculators", {}).keys()),
                )
            ),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return


@app.cell
def _(InMemoryRowDataSink, api, demand_ir, plan, runtime_bindings):
    # ③ execution facade 闭环：ExecutionRequest（内存 sink）→ run_ir → 取回行数据。
    sink = InMemoryRowDataSink()
    request = api.ExecutionRequest(
        export_layout=api.export_layout_from_demand_ir(demand_ir, plan.target_fields),
        output=api.OutputSpec(path=None),
        sink=sink,
        runtime_bindings=runtime_bindings,
        batch_size=10,
        parallel_mode="seq",
    )
    _ = api.run_ir(demand_ir, request)
    rows = sink.get_data()

    print("rows =", len(rows), "first =", rows[0] if rows else None)
    return (rows,)


@app.cell
def _(render_checks, rows):
    # ④ 断言展开
    checks = {
        "rows == 3": len(rows) == 3,
        "首行 value_plus_one == 2": bool(rows) and rows[0].get("value_plus_one") == 2,
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, make_chapter_result, rows, symbols):
    passed = bool(all(checks.values()))
    summary = "rows={}".format(len(rows))
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"rows": 3, "first_value_plus_one": 2}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "first_row": rows[0] if rows else None,
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
