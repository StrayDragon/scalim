"""Cells-native: ch120_derived_set_aggregations — count_distinct (+ migration notes)."""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""# Derived Set Aggregations: `count_distinct`

演示 `DerivedGroupBySpec` + `count_distinct`。

**已移除**（BREAKING）: `DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec`。

迁移替代:
- 去重 → loader / 上游先去重，或接受重复行后只用 `DerivedGroupBySpec`
- 两阶段聚合 → workflow 两个 demand/run（中间表 → 再聚合）
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

    ensure_repo_root_on_sys_path(__file__)
    return


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
    )
    from scalim.execution import ExecutionRequest, ExportLayout, OutputSpec, export_layout_from_demand_ir, run_ir
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.derived_set_aggregations_demo import (
        DerivedSetAggregationsDemoResult,
        verify_derived_set_aggregations_workbook,
    )
    from scalim_misc.demo_big_data_report.loaders import get_config, set_config
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model, build_ecommerce_runtime_bindings

    return (
        AggMetricSpec,
        AuditSheetSpec,
        DerivedGroupBySpec,
        DerivedOutputTargetSpec,
        DerivedSetAggregationsDemoResult,
        Dict,
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
        run_ir,
        set_config,
        tempfile,
        verify_derived_set_aggregations_workbook,
    )


@app.cell
def _(build_test_config_small, get_config, set_config):
    prev = get_config()
    cfg = build_test_config_small()
    set_config(cfg)
    return cfg, prev


@app.cell
def _(build_ecommerce_model, build_ecommerce_runtime_bindings, cfg):
    demand_ir = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    return demand_ir, runtime_bindings


@app.cell
def _(
    AggMetricSpec,
    AuditSheetSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    ExecutionRequest,
    ExportLayout,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputSpec,
    OutputTargetSpec,
    Path,
    demand_ir,
    export_layout_from_demand_ir,
    run_ir,
    runtime_bindings,
    tempfile,
    verify_derived_set_aggregations_workbook,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        wb_path = tp / "derived_set_aggregations_demo.xlsx"

        detail_fields = ("order_id", "customer_name", "product_name", "payment_method_name")
        detail_layout = export_layout_from_demand_ir(demand_ir, detail_fields)
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

        oracle = verify_derived_set_aggregations_workbook(str(wb_path))

    passed = bool(oracle.passed)
    summary = "passed={} sheets={} detail_rows={}".format(passed, len(oracle.sheet_names), len(oracle.detail_rows))
    if not passed:
        summary = summary + "\n" + oracle.message

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {"workbook_path": str(wb_path), "oracle_result": oracle},
    }
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
