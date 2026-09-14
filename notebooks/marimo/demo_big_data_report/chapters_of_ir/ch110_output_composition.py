"""Cells-native: ch110_output_composition — derived outputs workbook composition.

设计目标（对齐 repo 金标准 `example_readme_suite/ch010_min_python`）:
- 本章复用 `build_ecommerce_model` / `build_ecommerce_runtime_bindings` 作为**复杂复用零件**,
  但主线装配 `OutputCompositionSpec → run_ir → 对拍` 全部在 cells 内**逐 cell 展开**,
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
        # demo_big_data_report / ch110_output_composition

        本章演示 **OutputCompositionSpec** 构建多 sheet 工作簿:
        Detail(明细,主输出) + Summary(按类目汇总/排名) + Meta(元信息) + Audit(审计)。

        > 沿用完整电商模型(复杂复用零件),但把主线装配**摊开在 cells 里**观察"怎么写"。

        主线装配过程(每个步骤一个 cell,可就地修改重跑):
        1. 保存/恢复全局配置(`get_config`/`set_config`) + `build_test_config_small()` 构建测试配置
        2. `build_ecommerce_model(cfg)` 构建 `DemandIr` + `build_ecommerce_runtime_bindings()`(复杂复用零件)
        3. **(模型窥视)** 渲染 `demand_ir.fields` / 数据源(读者无需跳库)
        4. 构建 `OutputCompositionSpec`:primary detail + derived summary(分组/聚合/排名) + meta + audit
        5. `run_ir(demand_ir, ExecutionRequest(output_composition=...))` 执行并写出工作簿
        6. `verify_derived_outputs_workbook` 对拍 + `make_chapter_result` 产出 `chapter_result`(含 `expected`)

        > 下方的**模型窥视 cell** 会把复用零件的装配产物(字段/数据源)直接渲染出来。

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
    from typing import Dict

    from scalim.execution.output_composition import (
        AggMetricSpec,
        AuditSheetSpec,
        DerivedGroupBySpec,
        DerivedOutputTargetSpec,
        MetaSheetSpec,
        OutputCompositionSpec,
        OutputTargetSpec,
        RankFieldSpec,
    )
    from scalim.execution import ExecutionRequest, ExportLayout, OutputSpec, export_layout_from_demand_ir, run_ir
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.derived_outputs_demo import (
        DETAIL_FIELDS,
        SUMMARY_FIELDS,
        DerivedOutputsDemoResult,
        verify_derived_outputs_workbook,
    )
    from scalim_misc.demo_big_data_report.loaders import get_config, set_config
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model, build_ecommerce_runtime_bindings
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        AggMetricSpec,
        AuditSheetSpec,
        DerivedGroupBySpec,
        DerivedOutputTargetSpec,
        DerivedOutputsDemoResult,
        Dict,
        ExecutionRequest,
        ExportLayout,
        MetaSheetSpec,
        OutputCompositionSpec,
        OutputSpec,
        OutputTargetSpec,
        Path,
        RankFieldSpec,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        DETAIL_FIELDS,
        SUMMARY_FIELDS,
        export_layout_from_demand_ir,
        get_config,
        make_chapter_result,
        run_ir,
        set_config,
        tempfile,
        verify_derived_outputs_workbook,
    )


@app.cell
def _(build_test_config_small, get_config, set_config):
    # ① 保存/恢复全局配置 + 构建测试配置(复用零件:配置即数据场景)
    prev = get_config()
    cfg = build_test_config_small()
    set_config(cfg)
    return cfg, prev


@app.cell
def _(build_ecommerce_model, build_ecommerce_runtime_bindings, cfg):
    # ② 复用零件装配:完整电商 IR 模型 + 运行时注入(多源/多级 Join/派生字段)
    demand_ir = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    return demand_ir, runtime_bindings


@app.cell(hide_code=True)
def _(demand_ir, mo, runtime_bindings):
    # ③ 模型窥视(读者无需跳库):把复用零件的装配产物直接渲染出来
    #    - `demand_ir.fields` 是 mappingproxy(键=field_id),遍历用 `.values()`
    #    - `DerivedFieldIr` 可能无 `source_id`,用 `getattr` 兜底
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in demand_ir.fields.values()
    ]
    source_summary = [{"source_id": sid} for sid in demand_ir.sources.keys()]
    # 运行时接线(`runtime_bindings`)的键/目标:loader 注入点与派生计算函数注入点
    derived_keys = list(getattr(runtime_bindings, "derived_calculators", {}).keys())
    main_loader_keys = list(getattr(runtime_bindings, "main_source_loaders", {}).keys())
    source_loader_keys = list(getattr(runtime_bindings, "source_loaders", {}).keys())
    bindings_summary = [
        {"bindings_key": "main_source_loaders", "targets": main_loader_keys},
        {"bindings_key": "source_loaders", "targets": source_loader_keys},
        {"bindings_key": "derived_calculators", "targets": derived_keys},
    ]
    mo.vstack(
        [
            mo.md(
                "**模型窥视（读者无需跳库）**:`build_ecommerce_model(cfg)` + `build_ecommerce_runtime_bindings()`"
                " 的装配产物如下(字段 / 数据源 / 运行时接线键):"
            ),
            mo.md("**字段结构(`demand_ir.fields`)**:"),
            mo.ui.table(fields_summary, selection=None),
            mo.md("**数据源(`demand_ir.sources`)**:"),
            mo.ui.table(source_summary, selection=None),
            mo.md("**运行时接线(`runtime_bindings`)**(loader / 派生计算函数注入键与目标):"),
            mo.ui.table(bindings_summary, selection=None),
        ]
    )
    return


@app.cell
def _(
    AggMetricSpec,
    AuditSheetSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    DETAIL_FIELDS,
    ExecutionRequest,
    ExportLayout,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputSpec,
    OutputTargetSpec,
    Path,
    RankFieldSpec,
    SUMMARY_FIELDS,
    demand_ir,
    export_layout_from_demand_ir,
    make_chapter_result,
    run_ir,
    runtime_bindings,
    tempfile,
    verify_derived_outputs_workbook,
):
    # ④ 输出组合:primary detail + derived summary(分组/聚合/排名) + meta + audit
    #    - export_layout_from_demand_ir: 从 DemandIr 派生出 detail 输出布局
    #    - OutputCompositionSpec: targets(primary) + derived_targets(分组聚合/排名) + meta/audit sheet
    #    - run_ir + ExecutionRequest(output_composition=composition): 执行并写出 xlsx 工作簿
    #    - verify_derived_outputs_workbook: 对拍 oracle(数据校验逻辑,可复用零件)
    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        wb_path = tp / "derived_outputs_demo.xlsx"

        detail_layout = export_layout_from_demand_ir(demand_ir, DETAIL_FIELDS)
        summary_layout = ExportLayout(field_ids=SUMMARY_FIELDS, header_names=None)

        composition = OutputCompositionSpec(
            targets=(
                OutputTargetSpec(
                    target_id="detail",
                    layout=detail_layout,
                    output=OutputSpec(format="excel", path=str(wb_path), streaming=True, include_header=True, sheet_name="Detail"),
                    is_primary=True,
                ),
            ),
            derived_targets=(
                DerivedOutputTargetSpec(
                    target_id="summary_by_payment",
                    derived=DerivedGroupBySpec(
                        group_by=("payment_method_name",),
                        metrics=(
                            AggMetricSpec(out_field_id="order_cnt", op="count", field_id="order_id"),
                            AggMetricSpec(out_field_id="sum_amount", op="sum", field_id="order_amount"),
                            AggMetricSpec(out_field_id="sum_profit", op="sum", field_id="profit"),
                        ),
                        rank_fields=(RankFieldSpec(out_field_id="rank", kind="row_number", by="sum_profit", order="desc"),),
                    ),
                    output_layout=summary_layout,
                    output=OutputSpec(format="excel", path=str(wb_path), streaming=True, include_header=True, sheet_name="Summary"),
                ),
            ),
            meta_sheet=MetaSheetSpec(
                target_id="meta",
                output=OutputSpec(format="excel", path=str(wb_path), streaming=True, include_header=True),
                sheet_name="Meta",
            ),
            audit_sheet=AuditSheetSpec(
                target_id="audit",
                output=OutputSpec(format="excel", path=str(wb_path), streaming=True, include_header=True),
                sheet_name="Audit",
            ),
            failure_policy="all_fail",
        )

        core = run_ir(
            demand_ir,
            ExecutionRequest(
                export_layout=detail_layout,
                output=OutputSpec(path=None),
                sink=None,
                output_composition=composition,
                parallel_mode="seq",
                batch_size=10,
                runtime_bindings=runtime_bindings,
            ),
        )

        oracle = verify_derived_outputs_workbook(str(wb_path), outputs=dict(core.outputs or {}), total_rows=int(core.total_rows))

    # ⑤ 对拍断言 + 结构化 chapter_result(r1114: details 含 expected 前缀键)
    passed = bool(oracle.passed)
    summary = "passed={} sheets={} rows={}".format(passed, len(oracle.sheet_names), oracle.total_rows)
    if not passed:
        summary = summary + "\n" + oracle.detail_verification.summary + "\n" + oracle.summary_message

    # 对拍期望(教学 payload;headless 可经 details["expected"] 键定位)
    expected = {
        "oracle_passed": bool(oracle.passed),
        "total_rows": int(core.total_rows),
        "sheets": len(oracle.sheet_names),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "workbook_path": str(wb_path),
            "outputs": dict(core.outputs or {}),
            "total_rows": int(core.total_rows),
            "oracle_result": oracle,
        },
    )
    return chapter_result, oracle, passed, summary


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


@app.cell
def _(prev, set_config):
    set_config(prev)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
