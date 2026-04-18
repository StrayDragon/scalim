import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

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
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_SHEET_DETAIL = "Detail"
_SHEET_SUMMARY = "Summary"
_SHEET_META = "Meta"
_SHEET_AUDIT = "Audit"


def _build_composition(*, workbook_path: str, detail_layout: ExportLayout, summary_layout: ExportLayout) -> OutputCompositionSpec:
    return OutputCompositionSpec(
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
                target_id="summary_by_payment",
                derived=DerivedGroupBySpec(
                    group_by=("payment_method_name",),
                    metrics=(
                        AggMetricSpec(out_field_id="order_cnt", op="count", field_id="order_id"),
                        AggMetricSpec(out_field_id="sum_amount", op="sum", field_id="order_amount"),
                        AggMetricSpec(out_field_id="sum_profit", op="sum", field_id="profit"),
                    ),
                    rank_fields=(RankFieldSpec(out_field_id="rank", kind="row_number", by="sum_profit", order="desc"),),
                    max_groups=100,
                ),
                output_layout=summary_layout,
                output=OutputSpec(
                    format="excel",
                    path=str(workbook_path),
                    streaming=True,
                    include_header=True,
                    sheet_name=_SHEET_SUMMARY,
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


def run_output_composition(*, tmp_path: Optional[Path] = None) -> ExampleResult:
    if tmp_path is None:
        with tempfile.TemporaryDirectory() as tmpdir:
            return run_output_composition(tmp_path=Path(tmpdir))
    workbook_path = tmp_path / "derived_outputs_demo.xlsx"
    prev_config = get_config()
    set_config(build_test_config_small())
    try:
        demand_ir = build_ecommerce_model()
        runtime_bindings = build_ecommerce_runtime_bindings()
        detail_layout = export_layout_from_demand_ir(demand_ir, DETAIL_FIELDS)
        summary_layout = ExportLayout(field_ids=SUMMARY_FIELDS, header_names=None)
        composition = _build_composition(workbook_path=str(workbook_path), detail_layout=detail_layout, summary_layout=summary_layout)

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

        oracle_result: DerivedOutputsDemoResult = verify_derived_outputs_workbook(
            str(workbook_path),
            outputs=dict(core.outputs or {}),
            total_rows=int(core.total_rows),
        )
        passed = bool(oracle_result.passed)
        summary = "passed={} sheets={} rows={}".format(passed, len(oracle_result.sheet_names), oracle_result.total_rows)
        if not passed:
            summary = summary + "\n" + oracle_result.detail_verification.summary + "\n" + oracle_result.summary_message
        details: Dict[str, Any] = {
            "workbook_path": str(workbook_path),
            "outputs": dict(core.outputs or {}),
            "total_rows": int(core.total_rows),
            "oracle_result": oracle_result,
        }
    finally:
        set_config(prev_config)
    return ExampleResult(
        example_id="demo_big_data_report/ch110_output_composition",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_output_composition()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch110_output_composition

        本章目标:
        - 演示 composed outputs(workbook) 的端到端写出与对拍口径

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch110_output_composition.py::run_output_composition`

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
        result = run_output_composition(tmp_path=Path(tmpdir))
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
