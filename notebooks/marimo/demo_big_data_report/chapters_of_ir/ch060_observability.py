"""Cells-native marimo notebook: ch060_observability (observability chapter).

改写目标（对齐 repo 金标准 `example_readme_suite/ch010_min_python` 与主教程
`ch010_basics` 的 cells-native 内联模式）:
- 本章演示在 ScalimEngine 上注册四种 observer 并收集观测指标。
- 完整电商 model 属于**复杂可复用零件**,保留对 `scalim_misc.demo_big_data_report.shared`
  的 `build_ecommerce_model` / `build_ecommerce_runtime_bindings` 库调用（零件复用,不外移
  scalim 装配）。
- 但仍新增 "模型窥视" cell,把 `demand.fields` / `plan.metadata` / 派生计算器 / targets
  直接渲染在 notebook 内,读者无需跳库即可看到装配产物。
- 装配、observer 注册、Engine 运行、期望 vs 实际对拍全部在 cells 内可见。
- 通过 `chapter_result` 变量向 headless runner / pytest 暴露对拍结果。

本文件模块级代码仅保留:
  - `app = marimo.App(...)`
  - `run_chapter()` 薄适配层
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch060_observability

        注册 **四种 observer** 到 `ScalimEngine` 并验证观测指标收集无误。

        本章的 scalim 装配（model / 计划 / 运行时接线 / observer / 引擎运行 / 对拍）
        一步步摊开在下方 cells 内；完整电商 model 是**复杂可复用零件**（多源关联/多级 Join/
        派生字段），保留对 `scalim_misc` 库 builder 的调用，但用 "模型窥视" cell 把装配产物
        直接渲染出来，读者**无需跳库**。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：
        1. 读取测试配置 `build_test_config_small()` 并选取 12 个目标字段
        2. `build_ecommerce_model(cfg)` 构造 `DemandIr` + `build_ecommerce_runtime_bindings()`
           接线 + `PlanBuilder(demand).build(targets=...)` 生成执行计划
        3. **模型窥视**：渲染 `demand.fields` 结构、`plan.metadata`、派生计算器、targets 数量
        4. 注册四种 observer（Performance / Relation / ExecutionTrace / RowGap）到 `ObserverManager`
        5. `ScalimEngine` 运行 → `InMemoryColumnSink` 收行 → `verify_scalim_output` 校验
        6. 期望 vs 实际对拍 → `make_chapter_result(passed, summary, details={..., "expected": ...})`

        对拍入口：`run_chapter()` → `app.run()` → `chapter_result`
        Gate：`just examples`
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
    from typing import Dict, Sequence

    # scalim 公开 API（跨章节一致，直接导入 scalim.*）
    from scalim.execution.engine import ScalimEngine
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.execution_trace import ExecutionTraceObserver
    from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
    from scalim.ob.presets.relations import RelationConfig, RelationObserver
    from scalim.ob.presets.row_gap import RowGapObserver
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink

    # 章节结果契约辅助（r1114：details 必须含 expected* 键）
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    # 可复用零件：测试配置 / 目标字段集 / 复杂 model builder / 数据校验 oracle
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output

    return (
        Dict,
        ExecutionTraceObserver,
        InMemoryColumnSink,
        ObserverManager,
        PerformanceConfig,
        PerformanceObserver,
        PlanBuilder,
        RelationConfig,
        RelationObserver,
        RowGapObserver,
        ScalimEngine,
        Sequence,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        make_chapter_result,
        render_checks,
        verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    # ① 读取测试配置并挑选 12 个目标字段。
    #   - build_test_config_small(): 构造小规模电商测试数据配置（可复用零件）。
    #   - TARGET_FIELDS_FULL: 本报表的全部可选字段名清单；此处截取前 12 个作为本章对拍目标。
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL[:12])
    print("cfg + targets({})".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    # ② 复杂可复用零件：完整电商 model + 运行时接线 + 执行计划。
    #   - build_ecommerce_model(cfg): 复用库 builder 构造多源/多级 Join/派生字段的 DemandIr。
    #     （它在库内完成 MainSourceIr / SourceIr / FieldIr / DerivedFieldIr 等 IR 装配。）
    #   - build_ecommerce_runtime_bindings(): 复用库 builder 把 loader / params_builder /
    #     派生计算函数注入到 RuntimeBindings（运行期注入点）。
    #   - PlanBuilder(demand).build(targets=targets): 依据 demand IR 与目标字段裁剪出执行计划
    #     （含 total_sources / total_fields 等元数据）。
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=targets)
    return demand, plan, runtime_bindings


@app.cell(hide_code=True)
def _(demand, mo, plan, runtime_bindings, targets):
    # ③ 模型窥视：把库 builder 的装配产物直接渲染在 notebook 内，读者无需跳库。
    #   - demand.fields 是 mappingproxy（键=field_id），必须用 .values() 遍历；
    #     DerivedFieldIr 可能没有 source_id，用 getattr 兜底。
    #   - plan.metadata 暴露 total_sources / total_fields 元数据。
    #   - runtime_bindings.derived_calculators 是 dict，取键即派生计算器清单。
    fields_summary = [
        {
            "field_id": f.field_id,
            "name": f.name,
            "source_id": getattr(f, "source_id", "-"),
            "kind": type(f).__name__,
        }
        for f in demand.fields.values()
    ]
    derived_keys = list(getattr(runtime_bindings, "derived_calculators", {}).keys())
    meta = plan.metadata
    mo.vstack(
        [
            mo.md("**模型窥视（读者无需跳库）**——以下为 `build_ecommerce_model` 的装配产物："),
            mo.md(
                "字段总数 `{}`（含派生 {} 个）；`plan.metadata`: total_sources={} total_fields={}；"
                "targets 数量 = {}；派生计算器 = {}；source_loaders = {}".format(
                    len(fields_summary),
                    sum(1 for f in fields_summary if f["kind"] == "DerivedFieldIr"),
                    meta.total_sources,
                    meta.total_fields,
                    len(targets),
                    derived_keys,
                    len(getattr(runtime_bindings, "source_loaders", {})),
                )
            ),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return


@app.cell
def _(
    ExecutionTraceObserver,
    InMemoryColumnSink,
    ObserverManager,
    PerformanceConfig,
    PerformanceObserver,
    RelationConfig,
    RelationObserver,
    RowGapObserver,
    ScalimEngine,
    demand,
    plan,
    runtime_bindings,
    targets,
    verify_scalim_output,
):
    # ④ 四种 observer 预设的职责（教学）：
    #   - PerformanceObserver: 观测执行性能（duration / memory），sampling_interval=1。
    #   - RelationObserver: 观测关联（lookup）命中/未命中，sampling_rate=1.0。
    #   - ExecutionTraceObserver: 记录执行批次（trace）与每个 loader 的统计。
    #   - RowGapObserver: 检测主源行在关联后是否出现数据缺口（expected/actual/missing）。
    perf_obs = PerformanceObserver(config=PerformanceConfig(metrics={"duration", "memory"}, sampling_interval=1, report_format="none"))
    rel_obs = RelationObserver(config=RelationConfig(sampling_rate=1.0, report_format="none"))
    trace_obs = ExecutionTraceObserver()
    gap_obs = RowGapObserver(primary_loader_name="orders", data_loader_names={"customers", "products"}, sample_limit=3)

    # ObserverManager 作为 observer 注册中心；Engine 通过它收集观测。
    observer_manager = ObserverManager()
    for ob in [perf_obs, rel_obs, trace_obs, gap_obs]:
        observer_manager.register(ob)

    # ⑤ 组装 ScalimEngine（注入 demand / plan / runtime_bindings / observer_manager）。
    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        observer_manager=observer_manager,
        batch_size=10,
    )

    # ⑥ 运行：InMemoryColumnSink 按 field_names=targets 收列，上下文管理器负责资源释放。
    with InMemoryColumnSink(field_names=targets) as mem_sink:
        engine.run(main_rows=None, sink=mem_sink)
        rows = mem_sink.get_rows()

    # ⑦ 数据校验 oracle（封装的是数据校验逻辑，非 scalim 装配，属可复用零件）。
    verification = verify_scalim_output(rows, fields_to_check=targets)
    metrics = perf_obs.get_metrics()
    rel_metrics = rel_obs.get_metrics()

    print("rows={} verify={}".format(len(rows), verification.passed))
    print(
        "trace_batches={} loader_stats={} rel_lookups={}".format(
            len(trace_obs.batches), len(metrics.loader_stats), rel_metrics.total_lookups
        )
    )
    print("gap_expected={} actual={} missing={}".format(gap_obs.total_expected, gap_obs.total_actual, gap_obs.total_missing))
    return gap_obs, metrics, rel_metrics, rows, trace_obs, verification


@app.cell
def _(gap_obs, make_chapter_result, metrics, rel_metrics, render_checks, rows, trace_obs, verification):
    # ⑧ 对拍断言：汇总 oracle 校验与各 observer 收集到的观测指标是否达标。
    checks = {
        "oracle 校验通过": bool(verification.passed),
        "trace 批次 > 0": len(trace_obs.batches) > 0,
        "loader 指标 > 0": len(metrics.loader_stats) > 0,
        "relation lookups > 0": int(rel_metrics.total_lookups) > 0,
        "gap 无缺口": int(gap_obs.total_missing) == 0,
    }
    render_checks(checks)
    passed = bool(all(checks.values()))
    summary = "rows={} verify={} trace_batches={} loader_metrics={} rel_lookups={} gap_expected={}".format(
        len(rows),
        verification.passed,
        len(trace_obs.batches),
        len(metrics.loader_stats),
        int(rel_metrics.total_lookups),
        gap_obs.total_expected,
    )

    # 对拍期望值快照（r1114：details 前缀 expected 键，供 headless/pytest 定位）。
    expected = {
        "rows_min": 1,
        "trace_batches_min": 1,
        "loader_metrics_min": 1,
        "rel_lookups_min": 1,
        "gap_missing": 0,
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "rows": len(rows),
            "trace_batches": len(trace_obs.batches),
            "loader_metrics_count": len(metrics.loader_stats),
            "rel_lookups": int(rel_metrics.total_lookups),
            "rel_hits": int(rel_metrics.hit_count),
            "rel_misses": int(rel_metrics.miss_count),
            "gap_expected": gap_obs.total_expected,
            "gap_actual": gap_obs.total_actual,
            "gap_missing": gap_obs.total_missing,
        },
    )
    return chapter_result, checks, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
        kind="success" if ok else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    d_rows = details_to_rows(chapter_result["details"])
    if d_rows:
        mo.ui.table(d_rows, selection=None)
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
