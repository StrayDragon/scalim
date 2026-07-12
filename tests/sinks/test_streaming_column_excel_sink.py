from pathlib import Path

import pytest
from openpyxl import load_workbook

from scalim.sinks import ColumnExcelSink, StreamingColumnExcelSink


def _read_matrix(path: Path):
    wb = load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb.active
        return [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def test_streaming_column_excel_matches_column_excel_with_row_windows(tmp_path: Path) -> None:
    field_names = ["id", "name", "score"]
    row_ids = list(range(20))
    hold_path = tmp_path / "hold.xlsx"
    stream_path = tmp_path / "stream.xlsx"

    hold = ColumnExcelSink(str(hold_path), field_names=field_names)
    hold.set_row_ids(row_ids)
    for name in field_names:
        hold.write_column(name, {r: "{}-{}".format(name, r) for r in row_ids})
    hold.close()

    stream = StreamingColumnExcelSink(str(stream_path), field_names=field_names)
    stream.set_row_ids(row_ids)
    for start in range(0, 20, 5):
        end = min(20, start + 5)
        win = row_ids[start:end]
        for name in field_names:
            stream.write_column(name, {r: "{}-{}".format(name, r) for r in win})
    stream.close()

    assert _read_matrix(hold_path) == _read_matrix(stream_path)
    assert stream._flushed_rows == 20


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_streaming_column_excel_incomplete_rows_fail_fast(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.xlsx"
    sink = StreamingColumnExcelSink(str(path), field_names=["a", "b"])
    sink.set_row_ids([1, 2])
    sink.write_column("a", {1: 1, 2: 2})
    with pytest.raises(RuntimeError, match="未齐备"):
        sink.close()


def test_streaming_column_excel_set_row_ids_once(tmp_path: Path) -> None:
    sink = StreamingColumnExcelSink(str(tmp_path / "x.xlsx"), field_names=["a"])
    sink.set_row_ids([1])
    with pytest.raises(RuntimeError, match="set_row_ids"):
        sink.set_row_ids([2])
