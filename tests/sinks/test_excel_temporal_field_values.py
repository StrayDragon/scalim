"""FieldValue temporal types through ExcelSink (c0-add-field-value-datetime)."""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from scalim.sinks import ExcelSink


def _read_cell(path: Path, coord: str = "A2"):
    wb = openpyxl.load_workbook(str(path), data_only=False)
    try:
        cell = wb.active[coord]
        return cell.value, cell.data_type, type(cell.value).__name__
    finally:
        wb.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("v_datetime", datetime(2024, 1, 2, 3, 4, 5)),
        ("v_date", date(2024, 1, 2)),
        ("v_time", time(3, 4, 5)),
        ("v_timedelta", timedelta(days=1, seconds=30)),
    ],
)
def test_excel_sink_writes_naive_temporal_as_excel_date(tmp_path: Path, field: str, value: object) -> None:
    path = tmp_path / "{}.xlsx".format(field)
    with ExcelSink(str(path), field_names=[field], include_header=True, allow_formulas=False) as sink:
        sink.write_row({field: value})  # type: ignore[arg-type]

    cell_value, data_type, _py = _read_cell(path)
    assert data_type == "d"
    assert not isinstance(cell_value, str)


def test_excel_sink_aware_datetime_fails_like_openpyxl(tmp_path: Path) -> None:
    path = tmp_path / "aware.xlsx"
    aware = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    with pytest.raises(TypeError, match=r"timezone"):
        with ExcelSink(str(path), field_names=["v"], include_header=True) as sink:
            sink.write_row({"v": aware})  # type: ignore[arg-type]


def test_excel_sink_preserves_numeric_bool_none(tmp_path: Path) -> None:
    path = tmp_path / "basics.xlsx"
    with ExcelSink(str(path), field_names=["i", "b", "n"], include_header=True) as sink:
        sink.write_row({"i": 42, "b": True, "n": None})

    wb = openpyxl.load_workbook(str(path), data_only=False)
    try:
        row = list(next(wb.active.iter_rows(min_row=2, max_row=2)))
        assert row[0].value == 42
        assert row[0].data_type == "n"
        assert row[1].value is True
        assert row[1].data_type == "b"
        assert row[2].value is None
    finally:
        wb.close()
