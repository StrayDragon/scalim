from typing import Any, Dict, List, Mapping, Sequence

from scalim.sinks import BaseRowSink, IColumnSink
from scalim.typedefs import FieldValue, RowData


class _RowCollectSink(BaseRowSink):
    def __init__(self) -> None:
        self.rows: List[RowData] = []
        self.closed = False

    def write_row(self, row: RowData) -> None:
        self.rows.append(dict(row))

    def close(self) -> None:
        self.closed = True


class _ColumnCollectSink(IColumnSink):
    def __init__(self) -> None:
        self.row_ids: List[Any] = []
        self.columns: Dict[str, Dict[Any, FieldValue]] = {}
        self.closed = False

    def set_row_ids(self, row_ids: List[Any]) -> None:
        self.row_ids.extend(row_ids)

    def write_column(self, field_key: str, values: Mapping[Any, FieldValue]) -> None:
        if field_key not in self.columns:
            self.columns[field_key] = {}
        self.columns[field_key].update(values)

    def write_columns(self, columns: Mapping[str, Mapping[Any, FieldValue]]) -> None:
        for field_key, values in columns.items():
            self.write_column(field_key, values)

    def close(self) -> None:
        self.closed = True

    def discard(self) -> None:
        self.row_ids = []
        self.columns = {}
        self.closed = False


def test_base_row_sink_write_batch() -> None:
    sink = _RowCollectSink()
    sink.write_batch([{"a": 1}, {"a": 2}])
    sink.close()

    assert sink.rows == [{"a": 1}, {"a": 2}]
    assert sink.closed is True


def test_column_sink_default_write_batch() -> None:
    sink = _ColumnCollectSink()
    sink.write_batch([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    sink.close()

    assert sink.columns["a"][0] == 1
    assert sink.columns["b"][1] == 4
    assert sink.closed is True
