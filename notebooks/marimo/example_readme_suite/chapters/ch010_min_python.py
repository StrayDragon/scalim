"""Cells-native marimo notebook: ch010_min_python.

迁移对照:
  Before: cells 薄壳调用 support/min_python.py::run_min_python()（IR 装配在零件里）
  After:  loader/派生函数/DemandIr 装配/Plan/Engine 运行/期望/断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch010_min_python

        最小可跑 Python IR（假数据闭环）。

        教程核心全部在下方 cells 内逐步展开（无需跳转 support 实现）：

        1. 数据 loader 与派生计算函数（用户侧代码的样子）
        2. `DemandIr` 装配：主源 orders + 字段 `order_id` / `amount` / 派生字段 `amount_x2`
        3. `PlanBuilder` + `RuntimeBindings` 接线
        4. `ScalimEngine` 运行 → 内存 sink 收行
        5. 期望 vs 实际对拍（3 行；`amount_x2 = 金额 * 2`）

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
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return make_chapter_result, render_checks


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
    )


@app.cell
def _():
    # ① 用户侧代码的样子：一个 loader + 一个派生计算函数
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
def _(CallBySpecIr, CallByValueIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr):
    # ② 声明需求 IR：主源 orders + 字段（含派生字段 amount_x2）
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
        name="orders_report",
    )
    return demand, orders


@app.cell
def _(PlanBuilder, RuntimeBindings, calc_amount_x2, demand, load_orders):
    # ③ 计划构建 + 运行时接线（loader / 计算函数注入点）
    plan = PlanBuilder(demand).build()
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": load_orders},
        derived_calculators={"amount_x2": calc_amount_x2},
    )
    return plan, runtime_bindings


@app.cell
def _(InMemoryRowDataSink, ScalimEngine, demand, plan, runtime_bindings):
    # ④ 组装引擎并运行（批大小 1000，顺序模式），内存 sink 收行
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
    return rows, sink


@app.cell
def _(mo, rows):
    # ⑤ 期望 vs 实际（期望值是教学 payload，直接写在 cells 里）
    expected_rows = [
        {"order_id": 1, "amount": 10.0, "amount_x2": 20.0},
        {"order_id": 2, "amount": 20.5, "amount_x2": 41.0},
        {"order_id": 3, "amount": 7.0, "amount_x2": 14.0},
    ]
    keys = ("order_id", "amount", "amount_x2")
    actual_rows = [{k: row.get(k) for k in keys} for row in rows]
    mo.vstack(
        [
            mo.md("**期望 vs 实际**（派生字段 `amount_x2 = 金额 * 2`）："),
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
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "rows": len(rows),
            "sample": rows[0] if rows else None,
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, checks, passed, summary


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
