from pathlib import Path

import pytest

from scalim.sinks import CSVSink, ColumnCSVSink, ColumnExcelSink, ExcelSink, ExcelWorkbookSink


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["csv-row", "csv-col"],
)
def test_csv_sinks_do_not_create_lockfiles(tmp_path: Path, sink_cls) -> None:
    output_path = tmp_path / "out.csv"
    if sink_cls is CSVSink:
        sink = CSVSink(str(output_path), field_names=["id"])
        sink.write_row({"id": 1})
    else:
        sink = ColumnCSVSink(str(output_path), ["id"])
        sink.set_row_ids([1])
        sink.write_column("id", {1: 1})
    sink.close()

    assert output_path.exists() is True
    assert list(tmp_path.rglob("*.scalim.lock")) == []


@pytest.mark.parametrize(
    "sink_cls",
    [ExcelSink, ColumnExcelSink],
    ids=["xlsx-row", "xlsx-col"],
)
def test_excel_sinks_do_not_create_lockfiles(tmp_path: Path, sink_cls) -> None:
    output_path = tmp_path / "out.xlsx"
    if sink_cls is ExcelSink:
        sink = ExcelSink(str(output_path), field_names=["id"])
        sink.write_row({"id": 1})
    else:
        sink = ColumnExcelSink(str(output_path), ["id"])
        sink.set_row_ids([1])
        sink.write_column("id", {1: 1})
    sink.close()

    assert output_path.exists() is True
    assert list(tmp_path.rglob("*.scalim.lock")) == []


def test_excel_workbook_sink_does_not_create_lockfiles(tmp_path: Path) -> None:
    output_path = tmp_path / "wb.xlsx"
    wb = ExcelWorkbookSink(str(output_path))
    sheet_sink = wb.create_sheet_row_sink("S", field_names=["id"])
    sheet_sink.write_row({"id": 1})
    sheet_sink.close()
    wb.close()

    assert output_path.exists() is True
    assert list(tmp_path.rglob("*.scalim.lock")) == []
