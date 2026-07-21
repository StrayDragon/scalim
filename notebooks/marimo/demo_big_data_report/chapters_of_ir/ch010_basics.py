"""
Cells-native marimo notebook: ch010_basics (pilot migration).

设计目标:
- 全部内容在 marimo cells 内书写(渐进式探索 + 就地可视化)
- 通过 `chapter_result` 变量向 headless runner / pytest 暴露对拍结果
- `run_chapter()` 兼容层: `app.run()` → `chapter_result`
- 与现有 ChapterRegistry / just examples / pytest 完全兼容

迁移对照:
  Before: 模块级 run_basics() + 薄壳 cells (import → call → display)
  After:   cells 内逐步展开(配置 → 模型 → 计划 → 执行 → 验证 → 汇总)
           run_chapter() 作为薄兼容层调用 app.run()

本文件的模块级代码仅保留:
  - app = marimo.App(...)
  - run_chapter() 头兼容层
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


# ═══════════════════════════════════════════════════════════════
# Cell 1 — 教学目标
# ═══════════════════════════════════════════════════════════════


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch010_basics

        本章走一遍 Scalim 最小主线:

        ```
        Config → IR Model → Plan → Engine → Sink → Verification
        ```

        每个步骤是一个独立的 cell,你可就地修改参数、查看中间结果、
        或重新执行特定 cell 来定位问题。

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
        """
    )
    return


# ═══════════════════════════════════════════════════════════════
# Cell 2 — marimo 自身
# ═══════════════════════════════════════════════════════════════


@app.cell
def _():
    import marimo as mo

    return (mo,)


# ═══════════════════════════════════════════════════════════════
# Cell 3 — 仓库路径设置(notebook 辅助)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    return


# ═══════════════════════════════════════════════════════════════
# Cell 4 — 业务 imports
#
# app.run() 创建全新 __main__ 上下文,因此 imports 需在 cells 内完成。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _():
    import time

    from scalim.execution.engine import ScalimEngine
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.loaders import load_orders
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import (
        verify_order_by,
        verify_scalim_output,
    )

    return (
        InMemoryColumnSink,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        load_orders,
        time,
        verify_order_by,
        verify_scalim_output,
    )


# ═══════════════════════════════════════════════════════════════
# Cell 5 — 构建测试配置
#
# 你可以修改 cfg 参数来探索不同规模的场景。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(build_test_config_small):
    cfg = build_test_config_small()
    cfg
    return (cfg,)


# ═══════════════════════════════════════════════════════════════
# Cell 6 — 构建 IR Model + Runtime Bindings
#
# demand 是 IR 模型定义, runtime_bindings 是加载器/计算器注册表。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(build_ecommerce_model, build_ecommerce_runtime_bindings, cfg):
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()

    print("demand.fields: {}".format(len(demand.fields)))
    print("runtime_bindings.main_source: orders")
    print("runtime_bindings.derived_calculators: {}".format(list(runtime_bindings.derived_calculators.keys())))

    return demand, runtime_bindings


# ═══════════════════════════════════════════════════════════════
# Cell 7 — 构建 Plan
#
# PlanBuilder 将 IR model 编译为执行计划。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(PlanBuilder, TARGET_FIELDS_FULL, demand):
    targets = list(TARGET_FIELDS_FULL)
    plan = PlanBuilder(demand).build(targets=targets)

    print("plan.metadata.total_fields: {}".format(plan.metadata.total_fields))
    print("plan.metadata.total_sources: {}".format(plan.metadata.total_sources))
    print("targets: {}".format(targets))

    return plan, targets


# ═══════════════════════════════════════════════════════════════
# Cell 8 — 加载数据 + 创建 Engine + 执行
#
# 你可以调整 batch_size 来观察分批行为。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(InMemoryColumnSink, ScalimEngine, demand, load_orders, plan, runtime_bindings, targets, time):
    main_rows = list(load_orders())
    batch_size = 10

    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        batch_size=batch_size,
    )

    t0 = time.perf_counter()
    with InMemoryColumnSink(field_names=targets) as sink:
        engine.run(main_rows=main_rows, sink=sink)
        results = list(sink.get_rows())
    elapsed = time.perf_counter() - t0

    print("loaded {} rows, produced {} rows in {:.3f}s".format(len(main_rows), len(results), elapsed))

    return batch_size, elapsed, engine, main_rows, results, t0


# ═══════════════════════════════════════════════════════════════
# Cell 9 — 对拍验证
#
# 使用 oracle 验证输出正确性 + order_id 排序约束。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(results, targets, verify_order_by, verify_scalim_output):
    verification = verify_scalim_output(results, fields_to_check=targets)
    order_by = verify_order_by(results, ["order_id"])

    print("verify_scalim_output: {}".format("PASS" if verification.passed else "FAIL"))
    print("verify_order_by:       {}".format("PASS" if order_by.passed else "FAIL"))
    if not verification.passed:
        print("  verification detail:", verification.summary)
    if not order_by.passed:
        print("  order_by detail:", order_by.message)

    return order_by, verification


# ═══════════════════════════════════════════════════════════════
# Cell 10 — 汇总 chapter_result (CI 提取点)
#
# 命名约定: chapter_result (非 _ 前缀,app.run() 的 defs 可见)
# 契约: {"passed": bool, "summary": str, "details": dict|None}
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(elapsed, order_by, plan, results, targets, verification):
    passed = bool(verification.passed and order_by.passed)
    summary = "rows={} elapsed={:.3f}s verify={} order_by={}".format(
        len(results),
        elapsed,
        verification.passed,
        order_by.passed,
    )

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {
            "elapsed_seconds": elapsed,
            "rows": len(results),
            "targets": targets,
            "plan_total_fields": plan.metadata.total_fields,
            "plan_total_sources": plan.metadata.total_sources,
            "verification": verification,
            "order_by": order_by,
        },
    }

    return chapter_result, passed, summary


# ═══════════════════════════════════════════════════════════════
# Cell 11 — 结果展示 (交互时可看到)
# ═══════════════════════════════════════════════════════════════


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
        kind="success" if ok else "danger",
    )
    return


# ═══════════════════════════════════════════════════════════════
# Cell 12 — 详情表格
# ═══════════════════════════════════════════════════════════════


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    if rows:
        mo.ui.table(rows, selection=None)
    return


# ═══════════════════════════════════════════════════════════════
# 兼容层: 模块级 SSOT 入口
#
# ChapterRegistry → import 本模块 → 查找 run_chapter() → 调用
# 内部调用 app.run(),从 defs 提取 chapter_result dict。
# ChapterRegistry._safe_run() 自动将 dict 包装为 ExampleResult。
# ═══════════════════════════════════════════════════════════════


def run_chapter():
    """SSOT 入口: headless runner / pytest 通过此函数执行对拍。

    Returns:
        dict: chapter_result,至少包含 {"passed": bool, "summary": str}
    """
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
