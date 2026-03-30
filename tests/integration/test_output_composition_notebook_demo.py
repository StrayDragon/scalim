from pathlib import Path

from scalim_misc.demo_big_data_report.derived_outputs_demo import run_derived_outputs_demo


def test_derived_outputs_demo_matches_python_verification(tmp_path: Path) -> None:
    workbook_path = tmp_path / "derived_outputs_demo.xlsx"

    result = run_derived_outputs_demo(str(workbook_path))

    assert result.passed
    assert result.workbook_path == str(workbook_path)
    assert result.sheet_names == ["Detail", "Summary", "Meta", "Audit"]
    assert result.outputs["detail"] == str(workbook_path)
    assert result.outputs["summary_by_payment"] == str(workbook_path)
    assert result.total_rows == len(result.detail_rows)
    assert len(result.summary_rows) == len(result.expected_summary_rows)
    assert result.summary_rows[0]["sum_amount"] == 8069.5
    assert all(row["sum_profit"] == 3669.5 for row in result.summary_rows)
