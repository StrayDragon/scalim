"""Cells-native: ch070_parallel_mode — sequential vs adaptive parallel execution.

设计目标（对齐 repo 金标准 `example_readme_suite/ch010_min_python`）:
- 本章复用 `build_ecommerce_model` / `build_ecommerce_runtime_bindings` 作为**复杂复用零件**,
  但在"模型窥视 cell"把装配产物直接渲染出来,读者无需跳库。
- 主线装配 `Plan → Engine(两种 parallel_mode) → Sink → 对拍` 全部在 cells 内**逐 cell 展开**。
- 通过 `chapter_result` 向 headless runner / pytest 暴露对拍结果（含 r1114 `expected` 快照）。
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch070_parallel_mode

        本章对比 **`parallel_mode="seq"`(顺序)** 与 **`parallel_mode="adaptive"`(自适应并行)**
        两种引擎执行模式:输出一致性 + 行数。

        > 沿用完整电商模型(复杂复用零件),但把主线装配**摊开在 cells 里**观察"怎么写"。

        主线装配过程(每个步骤一个 cell,可就地修改重跑):
        1. `build_test_config_small()` 构建测试配置 + 取出 `TARGET_FIELDS_FULL[:12]` 目标字段子集
        2. `build_ecommerce_model(cfg)` 构建 `DemandIr` + `build_ecommerce_runtime_bindings()`(复杂复用零件)
        3. `PlanBuilder(demand).build(targets=...)` 生成执行计划
        4. `ScalimEngine` 分别以 `seq` / `adaptive` 两种 `parallel_mode` 运行 → `InMemoryColumnSink` 收行
        5. `verify_scalim_output` 分别对拍两种模式输出
        6. `make_chapter_result` 产出 `chapter_result`(含 `expected` 快照)

        > 下方的**模型窥视 cell** 会把复用零件的装配产物(字段/元数据/运行时键)直接渲染出来。

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
    from typing import Dict, List, Sequence

    from scalim.execution.engine import ScalimEngine
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink
    from scalim.typedefs import RowData
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        Dict,
        InMemoryColumnSink,
        List,
        PlanBuilder,
        RowData,
        ScalimEngine,
        Sequence,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        make_chapter_result,
        verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    # ① 测试配置 + 目标字段子集:小规模配置 + 前 12 个目标列
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL[:12])
    print("cfg built, {} targets".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    # ② 复用零件装配:完整电商 IR 模型 + 运行时注入 + 执行计划
    #    - build_ecommerce_model: 多源/多级 Join/派生字段 的 DemandIr(复杂可复用零件)
    #    - build_ecommerce_runtime_bindings: 把 loader / 派生计算函数注入到运行时绑定
    #    - PlanBuilder(demand).build(targets): 依据目标字段子集生成执行计划(裁剪未用字段)
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
                "**模型窥视（读者无需跳库）**:复用零件装配产物的可见化。"
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
            mo.md("**目标字段子集数** `targets`: {n}".format(n=len(targets))),
        ]
    )
    return


@app.cell
def _(InMemoryColumnSink, ScalimEngine, demand, plan, runtime_bindings, targets, verify_scalim_output):
    # ④ 两种 parallel_mode 引擎运行 + 对拍
    #    - e_seq: parallel_mode="seq" —— 顺序执行,输出确定性最强
    #    - e_adp: parallel_mode="adaptive" —— 自适应并行,需与 seq 输出一致
    #    - verify_scalim_output: 对拍 oracle(数据校验逻辑,可复用零件)
    e_seq = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10, parallel_mode="seq")
    with InMemoryColumnSink(field_names=targets) as sink_seq:
        e_seq.run(main_rows=None, sink=sink_seq)
        rows_seq = sink_seq.get_rows()

    e_adp = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10, parallel_mode="adaptive")
    with InMemoryColumnSink(field_names=targets) as sink_adp:
        e_adp.run(main_rows=None, sink=sink_adp)
        rows_adp = sink_adp.get_rows()

    vr_seq = verify_scalim_output(rows_seq, fields_to_check=targets)
    vr_adp = verify_scalim_output(rows_adp, fields_to_check=targets)
    print("seq: {} rows verify={}  adaptive: {} rows verify={}".format(len(rows_seq), vr_seq.passed, len(rows_adp), vr_adp.passed))
    return rows_seq, rows_adp, vr_adp, vr_seq


@app.cell
def _(make_chapter_result, rows_adp, rows_seq, vr_adp, vr_seq):
    # ⑤ 对拍断言 + 结构化 chapter_result(r1114: details 含 expected 前缀键)
    passed = bool(vr_seq.passed and vr_adp.passed and len(rows_seq) > 0)
    summary = "rows={} verify_seq={} verify_adaptive={}".format(len(rows_seq), vr_seq.passed, vr_adp.passed)

    # 对拍期望(教学 payload;headless 可经 details["expected"] 键定位)
    expected = {
        "verify_seq_passed": bool(vr_seq.passed),
        "verify_adaptive_passed": bool(vr_adp.passed),
        "rows_gt_0": len(rows_seq) > 0,
        "rows_count": len(rows_seq),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "rows": len(rows_seq),
            "verify_seq": vr_seq,
            "verify_adaptive": vr_adp,
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
