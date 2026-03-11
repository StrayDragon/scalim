from pathlib import Path

import pytest

from scalim.execution.output_composition import (
    AggMetricSpec,
    AuditSheetSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputTargetSpec,
)
from scalim.execution.run_ir import ExecutionRequest, ExportLayout, OutputSpec, run_ir
from scalim.sinks.sink_excel import ExcelWorkbookSink
from tests.cases.minimal_ir import build_minimal_ir_case


def _read_workbook_sheet_names(path: Path) -> "list[str]":
    from openpyxl import load_workbook

    wb = load_workbook(str(path), read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _read_sheet_rows(path: Path, sheet_name: str) -> "list[list[object]]":
    from openpyxl import load_workbook

    wb = load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb[sheet_name]
        return [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def test_excel_workbook_sink_multi_sheet_and_conflict(tmp_path: Path) -> None:
    out = tmp_path / "report.xlsx"
    wb = ExcelWorkbookSink(str(out))
    s1 = wb.create_sheet_row_sink("Detail", field_names=["id"], header_names=["ID"], include_header=True)
    s1.write_row({"id": 1})

    s2 = wb.create_sheet_row_sink("Summary", field_names=["k", "v"], header_names=["K", "V"], include_header=True)
    s2.write_row({"k": "a", "v": 1})

    with pytest.raises(ValueError, match="Duplicate excel sheet name"):
        _ = wb.create_sheet_row_sink("Detail", field_names=["id"], header_names=["ID"], include_header=True)

    wb.close()
    assert out.exists()
    assert _read_workbook_sheet_names(out) == ["Detail", "Summary"]


def test_run_ir_output_composition_workbook_detail_and_summary(tmp_path: Path) -> None:
    case = build_minimal_ir_case()
    rows = case.main_rows()

    out = tmp_path / "report.xlsx"

    detail = OutputTargetSpec(
        target_id="detail",
        layout=ExportLayout(field_ids=("order_id", "order_source", "amount", "cost", "profit"), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True, sheet_name="Detail"),
        is_primary=True,
    )

    derived = DerivedOutputTargetSpec(
        target_id="summary_by_source",
        derived=DerivedGroupBySpec(
            group_by=("order_source",),
            metrics=(
                AggMetricSpec(out_field_id="order_cnt", op="count", field_id="order_id"),
                AggMetricSpec(out_field_id="sum_amount", op="sum", field_id="amount"),
                AggMetricSpec(out_field_id="sum_profit", op="sum", field_id="profit"),
            ),
            max_groups=100,
        ),
        output_layout=ExportLayout(field_ids=("order_source", "order_cnt", "sum_amount", "sum_profit"), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True, sheet_name="Summary"),
    )

    meta = MetaSheetSpec(
        target_id="meta",
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True),
        sheet_name="Meta",
    )
    audit = AuditSheetSpec(
        target_id="audit",
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True),
        sheet_name="Audit",
    )

    spec = OutputCompositionSpec(
        targets=(detail,),
        derived_targets=(derived,),
        meta_sheet=meta,
        audit_sheet=audit,
        failure_policy="all_fail",
    )

    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=None,
        output_composition=spec,
        parallel_mode="seq",
    )

    result = run_ir(case.demand, request)
    assert out.exists()
    assert result.outputs is not None
    assert result.outputs["detail"] == str(out)
    assert result.outputs["summary_by_source"] == str(out)
    assert result.total_rows == len(rows)

    sheet_names = _read_workbook_sheet_names(out)
    assert sheet_names == ["Detail", "Summary", "Meta", "Audit"]

    detail_rows = _read_sheet_rows(out, "Detail")
    # header + rows
    assert detail_rows[0][:2] == ["order_id", "order_source"]
    assert len(detail_rows) == len(rows) + 1

    summary_rows = _read_sheet_rows(out, "Summary")
    assert summary_rows[0] == ["order_source", "order_cnt", "sum_amount", "sum_profit"]
    assert len(summary_rows) >= 2


def test_output_composition_primary_only_disables_failed_derived(tmp_path: Path) -> None:
    case = build_minimal_ir_case()
    rows = case.main_rows()
    out = tmp_path / "report.xlsx"

    detail = OutputTargetSpec(
        target_id="detail",
        layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True, sheet_name="Detail"),
        is_primary=True,
    )

    derived = DerivedOutputTargetSpec(
        target_id="summary_overflow",
        derived=DerivedGroupBySpec(
            group_by=("order_id",),
            metrics=(AggMetricSpec(out_field_id="cnt", op="count", field_id="order_id"),),
            max_groups=1,  # overflow when more than 1 distinct key
        ),
        output_layout=ExportLayout(field_ids=("order_id", "cnt"), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True, sheet_name="Summary"),
    )

    spec = OutputCompositionSpec(
        targets=(detail,),
        derived_targets=(derived,),
        meta_sheet=MetaSheetSpec(target_id="meta", output=OutputSpec(format="excel", path=str(out)), sheet_name="Meta"),
        audit_sheet=AuditSheetSpec(target_id="audit", output=OutputSpec(format="excel", path=str(out)), sheet_name="Audit"),
        failure_policy="primary_only",
    )

    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=None,
        output_composition=spec,
        parallel_mode="seq",
    )
    result = run_ir(case.demand, request)

    assert out.exists()
    assert result.output_target_stats is not None
    derived_stat = [s for s in result.output_target_stats if s.target_id == "summary_overflow"][0]
    assert derived_stat.disabled is True
    assert derived_stat.error_count >= 1


def test_ranked_summary_orders_and_adds_rank(tmp_path: Path) -> None:
    case = build_minimal_ir_case()
    out = tmp_path / "report.xlsx"

    detail = OutputTargetSpec(
        target_id="detail",
        layout=ExportLayout(field_ids=("order_id", "order_source", "amount"), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True, sheet_name="Detail"),
        is_primary=True,
    )

    ranked = DerivedOutputTargetSpec(
        target_id="ranked_summary",
        derived=DerivedGroupBySpec(
            group_by=("order_source",),
            metrics=(AggMetricSpec(out_field_id="sum_amount", op="sum", field_id="amount"),),
            rank_by="sum_amount",
            rank_order="desc",
        ),
        output_layout=ExportLayout(field_ids=("order_source", "sum_amount", "rank"), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True, sheet_name="Rank"),
    )

    spec = OutputCompositionSpec(targets=(detail,), derived_targets=(ranked,))
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=None,
        output_composition=spec,
        parallel_mode="seq",
    )

    _ = run_ir(case.demand, request)

    rows = _read_sheet_rows(out, "Rank")
    assert rows[0] == ["order_source", "sum_amount", "rank"]
    assert rows[1][0] == "app"
    assert rows[1][2] == 1
