"""Cells-native marimo notebook: ch010_basics (cells-native-inline first lesson).

设计目标（对齐 repo 金标准 `chapters_of_ir/ch010_basics`）:
- 教程核心（loader / 派生计算函数 / DemandIr 装配 / Plan / Engine / 对拍断言）
  **全部写在 cells 内**,读者打开即可观察"怎么写",无需跳转 `scalim_misc` 库实现。
- 不再调用 `build_ecommerce_model` 等库 builder(那些留给后续 ch040+ 章节复用)。
- 通过 `chapter_result` 变量向 headless runner / pytest 暴露对拍结果。
- `run_chapter()` 薄兼容层: `app.run()` → `chapter_result`。

本文件模块级代码仅保留:
  - `app = marimo.App(...)`
  - `run_chapter()` 薄适配层
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # demo_big_data_report / ch010_basics

    本章用**最小可跑闭环**走一遍 Scalim 主线,把"怎么写"直接摊开在 cells 里
    (根 `README` 的「或直接用 Python 编写需求」核心代码块即 ①~④ 的投影, 止于 `engine.run`;
    ⑤/⑥ 对拍脚手架仅在章节内, README 给完整演示链接):

    ```
    loader/计算函数 → DemandIr 装配 → Plan → Engine → Sink → 对拍
    ```

    主线装配过程(每个步骤一个 cell,可就地修改重跑):
    1. 定义 loader 与派生计算函数(用户侧代码的样子)
    2. 组装 `DemandIr`:主源 orders + 字段 `order_id` / `amount` + 派生字段 `amount_x2`
    3. `PlanBuilder` + `RuntimeBindings` 接线
    4. `ScalimEngine` 运行 → 内存 sink 收行
    5. 期望 vs 实际对拍(3 行假数据;`amount_x2 = 金额 * 2`)

    > 本章不调用 `scalim_misc` 里的 `build_ecommerce_model` 等库 builder,
    > 而是直接在 cells 里构造,便于理解每一个装配细节。
    > 完整电商报表(多源关联/多级 Join/派生字段)见后续章节。

    对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
    Gate: `just examples`
    """)
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
    return


@app.cell
def _():
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryRowDataSink
    from scalim.spec.ir import (
        CallBySpecIr,
        CallByValueIr,
        DemandIr,
        DerivedFieldIr,
        FieldIr,
        MainSourceIr,
        RuntimeHandleIdIr,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        CallBySpecIr,
        CallByValueIr,
        DemandIr,
        DerivedFieldIr,
        FieldIr,
        InMemoryRowDataSink,
        MainSourceIr,
        PlanBuilder,
        RuntimeBindings,
        RuntimeHandleIdIr,
        ScalimEngine,
        make_chapter_result,
        render_checks,
    )


@app.cell
def _():
    # ① 用户侧代码的样子:一个 loader + 一个派生计算函数
    def load_orders():
        return [
            {"order_id": 1, "amount": 10.0},
            {"order_id": 2, "amount": 20.5},
            {"order_id": 3, "amount": 7.0},
        ]

    def calc_amount_x2(amount):
        return float(amount) * 2

    return calc_amount_x2, load_orders


@app.cell
def _(
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    MainSourceIr,
    RuntimeHandleIdIr,
):
    # ② 声明需求 IR:主源 orders + 字段(含派生字段 amount_x2)
    orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    demand = DemandIr.from_irs(
        sources=[],
        main_source=orders,
        fields=(
            FieldIr(field_id="order_id", name="订单ID", source_id=orders.source_id),
            FieldIr(field_id="amount", name="金额", source_id=orders.source_id),
            DerivedFieldIr(
                field_id="amount_x2",
                name="金额*2",
                dependencies=("amount",),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id="amount_x2.calculator"),
                    kwargs=(("amount", CallByValueIr(kind="field", value="amount")),),
                    field_names=("amount",),
                ),
            ),
        ),
        name="demo_big_data_report_ch010",
    )
    return (demand,)


@app.cell(hide_code=True)
def _(demand, mo):
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in demand.fields.values()
    ]
    mo.vstack(
        [
            mo.md("**`DemandIr` 装配可见**(主源与字段结构,读者无需跳库):"),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return


@app.cell
def _(PlanBuilder, RuntimeBindings, calc_amount_x2, demand, load_orders):
    # ③ 计划构建 + 运行时接线(loader / 计算函数注入点)
    plan = PlanBuilder(demand).build()
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": load_orders},
        derived_calculators={"amount_x2": calc_amount_x2},
    )
    return plan, runtime_bindings


@app.cell
def _(InMemoryRowDataSink, ScalimEngine, demand, plan, runtime_bindings):
    # ④ 组装引擎并运行(批大小 1000,顺序模式),内存 sink 收行
    # (README 核心投影止于本 cell: `engine.run` 之后为 ⑤/⑥ 对拍脚手架,见完整演示链接)
    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        batch_size=1000,
        parallel_mode="seq",
    )
    sink = InMemoryRowDataSink()
    engine.run(sink=sink)
    rows = list(sink.get_data())
    return (rows,)


@app.cell
def _(mo, rows):
    # ⑤ 期望 vs 实际(期望值是教学 payload,直接写在 cells 里)
    expected_rows = [
        {"order_id": 1, "amount": 10.0, "amount_x2": 20.0},
        {"order_id": 2, "amount": 20.5, "amount_x2": 41.0},
        {"order_id": 3, "amount": 7.0, "amount_x2": 14.0},
    ]
    keys = ("order_id", "amount", "amount_x2")
    actual_rows = [{k: row.get(k) for k in keys} for row in rows]
    mo.vstack(
        [
            mo.md("**期望 vs 实际**(派生字段 `amount_x2 = 金额 * 2`):"),
            mo.ui.table(
                [{"kind": "期望", **row} for row in expected_rows] + [{"kind": "实际", **row} for row in actual_rows],
                selection=None,
            ),
        ]
    )
    return actual_rows, expected_rows


@app.cell
def _(actual_rows, expected_rows, make_chapter_result, render_checks, rows):
    # ⑥ 对拍断言 + 结构化 chapter_result
    checks = {
        "运行 3 行假数据": len(rows) == 3,
        "期望行完全一致": actual_rows == expected_rows,
    }
    render_checks(checks)
    passed = bool(all(checks.values()))
    summary = "rows={} amount_x2[0]={}".format(len(rows), rows[0].get("amount_x2") if rows else None)

    # 对拍期望(教学 payload;headless 可经 details 键定位)
    expected = {"rows": 3, "amount_x2_first": 20.0}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "rows": len(rows),
            "sample": rows[0] if rows else None,
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return (chapter_result,)


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

    detail_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(detail_rows, selection=None) if detail_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner / pytest 通过此函数执行对拍。

    Returns:
        dict: chapter_result,至少包含 {"passed": bool, "summary": str}
    """
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
