"""Cells-native: ch120_derived_set_aggregations — count_distinct (+ migration notes).

改造说明(对齐 repo cells-native A+C 模式,参考 `ch040_sinks`):
- `build_ecommerce_model(cfg)` / `build_ecommerce_runtime_bindings()` 是**复杂复用零件**
  (多源/多级 Join/复合键/派生字段的详细装配在库里) ,保留在 `scalim_misc` 库中不动;
  但新增**模型窥视 cell** 直接把装配产物(`demand_ir.fields` / `runtime_bindings` 键 /
  输出布局字段)渲染出来,读者无需跳库即可看到 scalim 装配是怎样构成的。
- scalim 装配(输出组合 `OutputCompositionSpec` / 派生聚合 `DerivedGroupBySpec` /
  `ExportLayout`)、运行 `run_ir`、对拍断言逐 cell 写在本 notebook 内。
- 通过 `chapter_result` 变量向 headless runner / pytest 暴露对拍结果; 含 `expected` 期望键(r1114)。
- `run_chapter()` 薄兼容层: `app.run()` → `chapter_result`。
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # demo_big_data_report / ch120_derived_set_aggregations

    本章演示**派生集合聚合**:`DerivedGroupBySpec` + `AggMetricSpec(op="count_distinct")`,
    在主源 detail 之外产出一个**按支付方式分组的客户数去重**(`customer_cnt`)的派生输出目标。

    主线装配过程(每个步骤一个 cell,可就地修改重跑):
    1. 组装测试配置 `cfg`(30 单 / 10 客户 / ... 小型数据)并设置全局配置
    2. `build_ecommerce_model(cfg)` 构建多源电商 IR 模型; `build_ecommerce_runtime_bindings()` 注入运行时接线
       (复杂复用零件,细节装配在库中),下方"模型窥视" cell 直接渲染装配产物
    3. 目标字段集 `detail_fields` + `export_layout_from_demand_ir(...)` 生成 detail 输出布局
    4. `OutputCompositionSpec` 装配主输出 `detail` + 派生输出 `distinct_by_payment`
       (`DerivedGroupBySpec` + `count_distinct`)+ Meta / Audit 表
    5. `run_ir(demand_ir, ExecutionRequest(...))` 执行 → 写出 Excel workbook
    6. `verify_derived_set_aggregations_workbook` 对拍(Distinct 行 = 按支付方式计数的唯一客户数)
    7. 汇总 `chapter_result`(含 `expected` 期望键)

    **已移除**(BREAKING): `DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec`。
    迁移替代:
    - 去重 → loader / 上游先去重,或接受重复行后只用 `DerivedGroupBySpec`
    - 两阶段聚合 → workflow 两个 demand/run(中间表 → 再聚合)

    > 完整电商模型(多源/多级 Join/复合键/派生)的细节装配在 `scalim_misc.demo_big_data_report.shared`,
    > 作为**复杂复用零件**保留在库里;但"装配产物长什么样"由下方"模型窥视" cell 直接渲染,
    > 读者无需跳库即可看到 `demand_ir.fields` / `runtime_bindings` 键 / 输出布局字段。

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

    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    import tempfile
    from pathlib import Path

    # scalim 公开装配 API:输出组合(spec 族)+ 执行入口
    from scalim.execution import ExecutionRequest, ExportLayout, OutputSpec, export_layout_from_demand_ir, run_ir
    from scalim.execution.output_composition import (
        AggMetricSpec,
        AuditSheetSpec,
        DerivedGroupBySpec,
        DerivedOutputTargetSpec,
        MetaSheetSpec,
        OutputCompositionSpec,
        OutputTargetSpec,
    )

    # 复用零件:复杂电商模型 build_*(细节在库中)+ 派生聚合 demo 对拍
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.derived_set_aggregations_demo import (
        DerivedSetAggregationsDemoResult,
        verify_derived_set_aggregations_workbook,
    )
    from scalim_misc.demo_big_data_report.loaders import get_config, set_config
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model, build_ecommerce_runtime_bindings

    # 章节结果契约:结构化 chapter_result 构造器(含 `expected` 期望键)
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        AggMetricSpec,
        AuditSheetSpec,
        DerivedGroupBySpec,
        DerivedOutputTargetSpec,
        DerivedSetAggregationsDemoResult,
        ExecutionRequest,
        ExportLayout,
        MetaSheetSpec,
        OutputCompositionSpec,
        OutputSpec,
        OutputTargetSpec,
        Path,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        export_layout_from_demand_ir,
        get_config,
        make_chapter_result,
        run_ir,
        set_config,
        tempfile,
        verify_derived_set_aggregations_workbook,
    )


@app.cell
def _(build_test_config_small, get_config, set_config):
    # ① 组装测试配置并设置全局配置:小型数据集保证 CI 快速稳定(几何/行数都确定性可对拍)
    prev = get_config()
    cfg = build_test_config_small()
    set_config(cfg)
    print("cfg built: sources configured per build_test_config_small()")
    return (cfg, prev)


@app.cell
def _(build_ecommerce_model, build_ecommerce_runtime_bindings, cfg):
    # ② 复用零件:构建多源电商 IR 模型 + 运行时接线(主源 orders + 多级 Join + 派生字段,细节在库中)
    #    `build_ecommerce_model(cfg)` 返回 DemandIr;`build_ecommerce_runtime_bindings()` 返回配套注入点
    demand_ir = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    return (demand_ir, runtime_bindings)


@app.cell(hide_code=True)
def _(demand_ir, export_layout_from_demand_ir, mo, runtime_bindings):
    # ③ 模型窥视(读者无需跳库):把库 build_* 的装配产物直接渲染出来,读者打开即可看到 scalim 装配长什么样
    #    遍历 demand_ir.fields 时用 .values()(它是 mappingproxy,键=field_id);
    #    DerivedFieldIr 可能没有 source_id,用 getattr(..., "source_id", "-") 兜底
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in demand_ir.fields.values()
    ]

    # 运行时接线键:读哪些 loader / 派生计算函数被绑定到哪些注入点
    main_loader_keys = list(getattr(runtime_bindings, "main_source_loaders", {}).keys())
    source_loader_keys = list(getattr(runtime_bindings, "source_loaders", {}).keys())
    derived_calc_keys = list(getattr(runtime_bindings, "derived_calculators", {}).keys())
    params_builder_keys = list(getattr(runtime_bindings, "params_builders", {}).keys())

    # 输出布局窥视:主 detail 目标字段集 + 对应导出布局(detail_fields 为"哪几列被导出")
    detail_fields = ("order_id", "customer_name", "product_name", "payment_method_name")
    detail_layout = export_layout_from_demand_ir(demand_ir, detail_fields)

    mo.vstack(
        [
            mo.md("**模型窥视(读者无需跳库)**: `build_ecommerce_model(cfg)` + `build_ecommerce_runtime_bindings()` 的装配产物"),
            mo.md(
                "`demand_ir.fields` = **{}** 个字段; `runtime_bindings`: `main_source_loaders`={} (共{}), "
                "`source_loaders`={} (共{}), `derived_calculators`={} (共{}), `params_builders`={} (共{}). "
                "detail 输出布局字段 = {}".format(
                    len(demand_ir.fields),
                    main_loader_keys,
                    len(main_loader_keys),
                    source_loader_keys,
                    len(source_loader_keys),
                    derived_calc_keys,
                    len(derived_calc_keys),
                    params_builder_keys,
                    len(params_builder_keys),
                    getattr(detail_layout, "field_ids", detail_fields),
                )
            ),
            mo.md("**`demand_ir.fields`(字段结构)**:"),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return (detail_fields, detail_layout, fields_summary)


@app.cell
def _(
    AggMetricSpec,
    AuditSheetSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    ExportLayout,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputSpec,
    OutputTargetSpec,
    Path,
    detail_fields,
    detail_layout,
    demand_ir,
    run_ir,
    runtime_bindings,
    tempfile,
    verify_derived_set_aggregations_workbook,
):
    # ④ 输出合成装配:主输出 `detail`(一个 Excel 工作簿)+ 派生输出 `distinct_by_payment`
    #    `DerivedGroupBySpec` 描述"按 payment_method_name 分组 + count_distinct(customer_name) → customer_cnt";
    #    `DerivedOutputTargetSpec` 把该派生聚合作为一个独立输出目标(写到 Distinct sheet)。
    #    `FailurePolicy="all_fail"` 表示任一目标失败即整章失败。
    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        wb_path = tp / "derived_set_aggregations_demo.xlsx"

        # 派生输出的目标列:payment_method_name + 派生统计字段 customer_cnt(header 缺省自动命名)
        distinct_layout = ExportLayout(field_ids=("payment_method_name", "customer_cnt"), header_names=None)

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
                    target_id="distinct_by_payment",
                    derived=DerivedGroupBySpec(
                        group_by=("payment_method_name",),
                        metrics=(AggMetricSpec(out_field_id="customer_cnt", op="count_distinct", field_id="customer_name"),),
                    ),
                    output_layout=distinct_layout,
                    output=OutputSpec(format="excel", path=str(wb_path), streaming=True, include_header=True, sheet_name="Distinct"),
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

        # ⑤ 引擎执行:run_ir(demand, ExecutionRequest(export_layout / output / sink / output_composition / runtime_bindings))
        #    `ExecutionRequest` 声明整体执行参数(顺序模式 + 批大小 10);`sink=None` 表示落盘路径模式。
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

        # ⑥ 对拍验证:读取写出 workbook,核对 Distinct 行 = 按支付方式计数得到的唯一客户数
        oracle = verify_derived_set_aggregations_workbook(str(wb_path))
        wb_path_str = str(wb_path)

    return (core, oracle, wb_path_str)


@app.cell
def _(make_chapter_result, oracle, wb_path_str):
    # ⑦ 汇总对拍结果:passed 由 oracle 决定;summary 一行概括;details 附上 `expected` 期望键(r1114)
    passed = bool(oracle.passed)
    summary = "passed={} sheets={} detail_rows={}".format(passed, len(oracle.sheet_names), len(oracle.detail_rows))
    if not passed:
        summary = summary + "\n" + oracle.message

    # 对拍期望(教学 payload;headless 可经 details["expected"] 定位)
    expected = {
        "passed": True,
        "sheet_names": oracle.sheet_names,
        "detail_rows": len(oracle.detail_rows),
        "distinct_rows": len(oracle.distinct_rows),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "workbook_path": wb_path_str,
            "oracle_result": oracle,
        },
    )
    return (chapter_result, expected, passed, summary)


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

    detail_rows = details_to_rows(chapter_result["details"])
    if detail_rows:
        mo.ui.table(detail_rows, selection=None)
    return


@app.cell
def _(prev, set_config):
    # 恢复全局配置(与单元运行前保持一致,避免影响同进程其它章节)
    set_config(prev)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
