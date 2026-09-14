"""Cells-native: ch050_memory_opt — memory optimization observer + block column CSV.

设计目标（对齐 repo 金标准 `example_readme_suite/ch010_min_python`）:
- 本章复用 `scalim_misc` 中 `build_ecommerce_model` / `build_ecommerce_runtime_bindings`
  作为**复杂复用零件**（多源/多级 Join/派生 的完整电商模型),符合 r1111 可复用边界。
- 但主线装配 `Plan → Engine → Observer → Sink → 对拍` 全部在 cells 内**逐 cell 展开**,
  并在"模型窥视 cell"把装配产物直接渲染出来,读者无需跳库。
- 通过 `chapter_result` 向 headless runner / pytest 暴露对拍结果（含 r1114 `expected` 快照）。
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch050_memory_opt

        本章演示 **MemoryOptimizationObserver(内存优化观察者)** + **BlockColumnCSVSink(分块列式 CSV 写出)**。

        > 沿用 `ch040` 起引入的完整电商模型,但把主线装配**摊开在 cells 里**观察"怎么写"。

        主线装配过程(每个步骤一个 cell,可就地修改重跑):
        1. `build_test_config_small()` 构建测试配置 + 取出 `TARGET_FIELDS_FULL` 目标字段集
        2. `build_ecommerce_model(cfg)` 构建 `DemandIr`(复杂复用零件,见"模型窥视"cell)
        3. `build_ecommerce_runtime_bindings()` 构建运行时注入(loader / 派生计算函数)
        4. `PlanBuilder(demand).build(targets=...)` 生成执行计划
        5. `ObserverManager` + `MemoryOptimizationObserver` 注册内存优化观察者
        6. `ScalimEngine` 三种写出演示:`ColumnCSVSink` / `InMemoryColumnSink` / `BlockColumnCSVSink`
        7. `verify_scalim_output` 对拍 + `make_chapter_result` 产出 `chapter_result`

        > 本章模型由 `scalim_misc.demo_big_data_report.shared` 的复杂复用零件构建,
        > 下方的**模型窥视 cell** 会把装配产物(字段/元数据/运行时键)直接渲染出来。

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
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
    import tempfile
    from pathlib import Path
    from typing import Dict, List

    from scalim.execution.engine import ScalimEngine
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.memory import MemoryOptimizationObserver
    from scalim.planning import PlanBuilder
    from scalim.sinks import BlockColumnCSVSink, ColumnCSVSink
    from scalim.sinks.memory import InMemoryColumnSink
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        BlockColumnCSVSink,
        ColumnCSVSink,
        Dict,
        InMemoryColumnSink,
        List,
        MemoryOptimizationObserver,
        ObserverManager,
        Path,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        make_chapter_result,
        tempfile,
        verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    # ① 测试配置 + 目标字段集:小规模配置 + 完整报表目标列
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL)
    print("cfg built, {} targets".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    # ② 复用零件装配:完整电商 IR 模型 + 运行时注入 + 执行计划
    #    - build_ecommerce_model: 多源/多级 Join/派生字段 的 DemandIr(复杂可复用零件)
    #    - build_ecommerce_runtime_bindings: 把 loader / 派生计算函数注入到运行时绑定
    #    - PlanBuilder(demand).build(targets): 依据目标字段生成执行计划(裁剪未用字段)
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=targets)
    print("demand.fields={} plan.sources={}".format(len(demand.fields), plan.metadata.total_sources))
    return demand, plan, runtime_bindings


@app.cell(hide_code=True)
def _(demand, mo, plan, runtime_bindings, targets):
    # ③ 模型窥视:把复用零件的装配产物直接渲染出来,读者无需跳库
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in demand.fields.values()
    ]
    derived_keys = list(getattr(runtime_bindings, "derived_calculators", {}).keys()) or list(runtime_bindings.derived_calculators.keys())
    mo.vstack(
        [
            mo.md(
                "**模型窥视（读者无需跳库）**:多源复用零件装配产物的可见化。"
                "`demand.fields` 为 mappingproxy(键=field_id),遍历用 `.values()`;"
                "`DerivedFieldIr` 可能无 `source_id`,用 `getattr` 兜底。"
            ),
            mo.md("**字段结构(`demand.fields`)**:"),
            mo.ui.table(fields_summary, selection=None),
            mo.md(
                "**计划元数据** `plan.metadata`:total_sources={total_sources}, total_fields={total_fields}".format(
                    total_sources=plan.metadata.total_sources, total_fields=plan.metadata.total_fields
                )
            ),
            mo.md("**运行时派生计算器键** `runtime_bindings.derived_calculators`: {keys}".format(keys=derived_keys)),
            mo.md("**目标字段数** `targets`: {n}".format(n=len(targets))),
        ]
    )
    return


@app.cell
def _(
    BlockColumnCSVSink,
    ColumnCSVSink,
    InMemoryColumnSink,
    MemoryOptimizationObserver,
    ObserverManager,
    ScalimEngine,
    demand,
    plan,
    runtime_bindings,
    targets,
    tempfile,
    verify_scalim_output,
):
    # ④ 内存优化观察者 + 三种 sink 写出演示
    #    - ObserverManager: 观察者管理器,用于注册/分发运行期事件
    #    - MemoryOptimizationObserver: 监听列写出/字段瘦身事件(内存优化观测)
    observer_manager = ObserverManager()
    mem_obs = MemoryOptimizationObserver()
    observer_manager.register(mem_obs)

    # ScalimEngine: 绑定 demand/plan/runtime_bindings/observer_manager 运行
    e1 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, observer_manager=observer_manager, batch_size=10)

    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        # 变体 A: ColumnCSVSink —— 逐列写出为 CSV(标准列式持久化)
        col_csv = tp / "column.csv"
        with ColumnCSVSink(str(col_csv), field_names=targets) as col_sink:
            e1.run(main_rows=None, sink=col_sink)

        # 变体 B: InMemoryColumnSink —— 纯内存列式收行(用于对拍,不写盘)
        e2 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with InMemoryColumnSink(field_names=targets) as mem_sink:
            e2.run(main_rows=None, sink=mem_sink)
            mem_results = mem_sink.get_rows()

        # verify_scalim_output: 对拍 oracle(数据校验逻辑,可复用零件)
        verification = verify_scalim_output(mem_results, fields_to_check=targets)

        # 变体 C: BlockColumnCSVSink —— 分块写出 CSV(带 write_delay,用于大结果节流/缓解峰值内存)
        block_csv = tp / "block.csv"
        e3 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with BlockColumnCSVSink(str(block_csv), field_names=targets[:10], write_delay=0.0) as block_sink:
            e3.run(main_rows=None, sink=block_sink)

    print(
        "mem_results={} verify={} col_write_events={} field_slim_events={}".format(
            len(mem_results), verification.passed, len(mem_obs.column_write_events), len(mem_obs.field_slim_events)
        )
    )
    return block_sink, mem_obs, mem_results, verification


@app.cell
def _(make_chapter_result, mem_obs, mem_results, targets, verification):
    # ⑤ 对拍断言 + 结构化 chapter_result(r1114: details 含 expected 前缀键)
    passed = bool(verification.passed and len(mem_obs.column_write_events) > 0)
    summary = "rows={} verify={} column_write_events={}".format(len(mem_results), verification.passed, len(mem_obs.column_write_events))
    if not verification.passed:
        summary = summary + "\n" + verification.summary

    # 对拍期望(教学 payload;headless 可经 details["expected"] 键定位)
    expected = {
        "verify_passed": bool(verification.passed),
        "rows_gt_0": len(mem_results) > 0,
        "column_write_events_gt_0": len(mem_obs.column_write_events) > 0,
        "targets": len(targets),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "rows": len(mem_results),
            "verification": verification,
            "column_write_events": len(mem_obs.column_write_events),
            "field_slim_events": len(mem_obs.field_slim_events),
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])), kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    d_rows = details_to_rows(chapter_result["details"])
    if d_rows:
        mo.ui.table(d_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
