import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from scalim.execution.output_composition import (
    AggMetricSpec,
    AuditSheetSpec,
    DedupBySpec,
    DerivedDedupByGroupBySpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputTargetSpec,
    TwoStageGroupBySpec,
)
from scalim.execution.run_ir import ExecutionRequest, ExportLayout, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.derived_set_aggregations_demo import (
    DerivedSetAggregationsDemoResult,
    verify_derived_set_aggregations_workbook,
)
from scalim_misc.demo_big_data_report.loaders import get_config, set_config
from scalim_misc.demo_big_data_report.shared import build_ecommerce_model
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_SHEET_DETAIL = "Detail"
_SHEET_DISTINCT = "Distinct"
_SHEET_DEDUP = "Dedup"
_SHEET_TWO_STAGE = "TwoStage"
_SHEET_META = "Meta"
_SHEET_AUDIT = "Audit"


def run_derived_set_aggregations(*, tmp_path: Optional[Path] = None) -> ExampleResult:
    if tmp_path is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            return run_derived_set_aggregations(tmp_path=Path(tmpdir))
    workbook_path = tmp_path / "derived_set_aggregations_demo.xlsx"
    prev_config = get_config()
    set_config(build_test_config_small())
    try:
        demand_ir = build_ecommerce_model()

        detail_fields = (
            "order_id",
            "customer_name",
            "product_name",
            "payment_method_name",
        )
        detail_layout = export_layout_from_demand_ir(demand_ir, detail_fields)

        distinct_layout = ExportLayout(field_ids=("payment_method_name", "customer_cnt"), header_names=None)
        two_stage_layout = ExportLayout(field_ids=("order_cnt", "customer_cnt"), header_names=None)

        composition = OutputCompositionSpec(
            targets=(
                OutputTargetSpec(
                    target_id="detail",
                    layout=detail_layout,
                    output=OutputSpec(
                        format="excel",
                        path=str(workbook_path),
                        streaming=True,
                        include_header=True,
                        sheet_name=_SHEET_DETAIL,
                    ),
                    is_primary=True,
                ),
            ),
            derived_targets=(
                DerivedOutputTargetSpec(
                    target_id="distinct_by_payment",
                    derived=DerivedGroupBySpec(
                        group_by=("payment_method_name",),
                        metrics=(AggMetricSpec(out_field_id="customer_cnt", op="count_distinct", field_id="customer_name"),),
                        max_distinct=100,
                        distinct_on_overflow="error",
                    ),
                    output_layout=distinct_layout,
                    output=OutputSpec(
                        format="excel",
                        path=str(workbook_path),
                        streaming=True,
                        include_header=True,
                        sheet_name=_SHEET_DISTINCT,
                    ),
                ),
                DerivedOutputTargetSpec(
                    target_id="dedup_customer_then_group",
                    derived=DerivedDedupByGroupBySpec(
                        dedup_by=DedupBySpec(
                            key_fields=("customer_name",),
                            on_conflict="first",
                            max_distinct=100,
                            on_overflow="truncate",
                        ),
                        group_by=DerivedGroupBySpec(
                            group_by=("payment_method_name",),
                            metrics=(AggMetricSpec(out_field_id="customer_cnt", op="count"),),
                        ),
                    ),
                    output_layout=distinct_layout,
                    output=OutputSpec(
                        format="excel",
                        path=str(workbook_path),
                        streaming=True,
                        include_header=True,
                        sheet_name=_SHEET_DEDUP,
                    ),
                ),
                DerivedOutputTargetSpec(
                    target_id="two_stage_customer_order_cnt_hist",
                    derived=TwoStageGroupBySpec(
                        stage1=DerivedGroupBySpec(
                            group_by=("customer_name",),
                            metrics=(
                                AggMetricSpec(out_field_id="order_cnt", op="count", field_id="order_id"),
                                AggMetricSpec(out_field_id="product_cnt", op="count_distinct", field_id="product_name"),
                            ),
                            max_distinct=100,
                            distinct_on_overflow="truncate",
                        ),
                        stage2=DerivedGroupBySpec(
                            group_by=("order_cnt",),
                            metrics=(AggMetricSpec(out_field_id="customer_cnt", op="count"),),
                        ),
                    ),
                    output_layout=two_stage_layout,
                    output=OutputSpec(
                        format="excel",
                        path=str(workbook_path),
                        streaming=True,
                        include_header=True,
                        sheet_name=_SHEET_TWO_STAGE,
                    ),
                ),
            ),
            meta_sheet=MetaSheetSpec(
                target_id="meta",
                output=OutputSpec(format="excel", path=str(workbook_path), streaming=True, include_header=True),
                sheet_name=_SHEET_META,
            ),
            audit_sheet=AuditSheetSpec(
                target_id="audit",
                output=OutputSpec(format="excel", path=str(workbook_path), streaming=True, include_header=True),
                sheet_name=_SHEET_AUDIT,
            ),
            failure_policy="all_fail",
        )

        _ = run_ir(
            demand_ir,
            ExecutionRequest(
                export_layout=detail_layout,
                output=OutputSpec(path=None),
                sink=None,
                output_composition=composition,
                parallel_mode="seq",
                batch_size=10,
            ),
        )

        oracle_result: DerivedSetAggregationsDemoResult = verify_derived_set_aggregations_workbook(str(workbook_path))
        passed = bool(oracle_result.passed)
        summary = "passed={} sheets={} detail_rows={}".format(passed, len(oracle_result.sheet_names), len(oracle_result.detail_rows))
        if not passed:
            summary = summary + "\n" + oracle_result.message
        details: Dict[str, Any] = {"workbook_path": str(workbook_path), "oracle_result": oracle_result}
    finally:
        set_config(prev_config)
    return ExampleResult(
        example_id="demo_big_data_report/ch120_derived_set_aggregations",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_derived_set_aggregations()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch120_derived_set_aggregations

        本章目标:
        - 演示派生聚合 set 口径的关键原语与护栏边界(可对拍)

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch120_derived_set_aggregations.py::run_derived_set_aggregations`

        Gate:
        - `just examples`（跑全量）
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import tempfile
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return Path, tempfile


@app.cell
def _(Path, tempfile):
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_derived_set_aggregations(tmp_path=Path(tmpdir))
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
