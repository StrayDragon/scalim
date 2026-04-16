import logging
import time
from pathlib import Path

import pytest

try:
    import pandas as pd
except Exception as exc:
    pytest.skip("pandas unavailable in this environment: {}".format(exc), allow_module_level=True)

from scalim.sinks import BaseColumnSink, BaseRowSink, BaseSink, IColumnSink, IRowSink
from scalim.sinks import (
    BlockColumnCSVSink,
    CSVSink,
    ColumnCSVSink,
)
from scalim.sinks._internal.sink_csv import COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED, CSV_SINK_REMOVE_TEMP_FILE_FAILED
from scalim.sinks.memory import InMemoryColumnSink
from scalim.sinks.pandas import PandasColumnSink, PandasRowSink


class _RowSink(IRowSink):
    def __init__(self) -> None:
        self.rows = []
        self.closed = False

    def write_row(self, row) -> None:  # type: ignore[override]
        self.rows.append(dict(row))

    def close(self) -> None:  # type: ignore[override]
        self.closed = True


class _ColumnSink(IColumnSink):
    def __init__(self) -> None:
        self.columns_called = False
        self.closed = False

    def set_row_ids(self, row_ids) -> None:  # type: ignore[override]
        return None

    def write_column(self, field_key, values) -> None:  # type: ignore[override]
        return None

    def write_columns(self, columns) -> None:  # type: ignore[override]
        self.columns_called = True

    def close(self) -> None:  # type: ignore[override]
        self.closed = True


class _ContextSink(BaseSink):
    def __init__(self) -> None:
        self.closed = False
        self.rows = []

    def write_batch(self, rows) -> None:  # type: ignore[override]
        self.rows = list(rows)

    def close(self) -> None:  # type: ignore[override]
        self.closed = True


def _write_csv_rows(output_path: Path, sink_cls, rows) -> None:
    if sink_cls is CSVSink:
        sink = CSVSink(str(output_path), field_names=["id", "name"])
        for row in rows:
            sink.write_row(row)
        sink.close()
        return

    sink = ColumnCSVSink(str(output_path), ["id", "name"])
    row_ids = [row["id"] for row in rows]
    sink.set_row_ids(row_ids)
    sink.write_column("id", {row["id"]: row["id"] for row in rows})
    sink.write_column("name", {row["id"]: row.get("name") for row in rows})
    sink.close()


def _write_csv_rows_with_context(output_path: Path, sink_cls, rows) -> None:
    if sink_cls is CSVSink:
        with CSVSink(str(output_path), field_names=["id", "name"]) as sink:
            for row in rows:
                sink.write_row(row)
        return

    with ColumnCSVSink(str(output_path), ["id", "name"]) as sink:
        row_ids = [row["id"] for row in rows]
        sink.set_row_ids(row_ids)
        sink.write_column("id", {row["id"]: row["id"] for row in rows})


def test_row_sink_default_write_batch() -> None:
    sink = _RowSink()
    sink.write_batch([{"id": 1}, {"id": 2}])
    sink.close()

    assert sink.rows == [{"id": 1}, {"id": 2}]
    assert sink.closed is True


def test_column_sink_write_batch_empty_returns() -> None:
    sink = _ColumnSink()
    sink.write_batch([])
    sink.close()

    assert sink.columns_called is False
    assert sink.closed is True


def test_base_sinks_raise_not_implemented() -> None:
    base_sink = BaseSink()
    with pytest.raises(NotImplementedError):
        base_sink.write_batch([])
    # close() now has default empty implementation
    base_sink.close()

    base_row_sink = BaseRowSink()
    with pytest.raises(NotImplementedError):
        base_row_sink.write_row({})
    # close() now has default empty implementation
    base_row_sink.close()


def test_base_column_sink_raises_not_implemented() -> None:
    base_column_sink = BaseColumnSink()
    assert base_column_sink.__enter__() is base_column_sink
    with pytest.raises(NotImplementedError):
        base_column_sink.set_row_ids([])
    with pytest.raises(NotImplementedError):
        base_column_sink.write_column("id", {})
    with pytest.raises(NotImplementedError):
        base_column_sink.write_columns({})
    # close() now has default empty implementation
    base_column_sink.close()
    # __exit__ calls close(), which now has default empty implementation
    base_column_sink.__exit__(None, None, None)


def test_base_sink_context_manager() -> None:
    with _ContextSink() as sink:
        sink.write_batch([{"id": 1}])

    assert sink.closed is True
    assert sink.rows == [{"id": 1}]


@pytest.mark.parametrize(
    "sink_cls,filename",
    [
        (CSVSink, "rows.csv"),
        (ColumnCSVSink, "cols.csv"),
    ],
    ids=["row-sink", "column-sink"],
)
def test_csv_sinks_handle_none_values(tmp_path: Path, sink_cls, filename: str) -> None:
    output_path = tmp_path / filename
    _write_csv_rows(output_path, sink_cls, [{"id": 1, "name": None}])

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "1,"


@pytest.mark.parametrize(
    "sink_cls,filename",
    [
        (CSVSink, "ctx_rows.csv"),
        (ColumnCSVSink, "ctx_cols.csv"),
    ],
    ids=["row-sink", "column-sink"],
)
def test_csv_sinks_context_manager(tmp_path: Path, sink_cls, filename: str) -> None:
    output_path = tmp_path / filename
    _write_csv_rows_with_context(output_path, sink_cls, [{"id": 1, "name": "A"}])
    assert output_path.exists()


def test_inmemory_column_sink_write_batch() -> None:
    sink = InMemoryColumnSink()
    sink.write_batch([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])

    assert sink.get_columns()["id"][0] == 1
    assert sink.get_columns()["name"][1] == "B"


def test_inmemory_column_sink_context_manager() -> None:
    with InMemoryColumnSink() as sink:
        sink.write_column("id", {0: 1})

    assert sink.get_columns()["id"][0] == 1


def test_pandas_sinks_empty_dataframes() -> None:
    row_sink = PandasRowSink()
    df = row_sink.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert df.empty

    col_sink = PandasColumnSink(field_names=["id", "name"])
    df_cols = col_sink.to_dataframe()
    assert list(df_cols.columns) == ["id", "name"]


def test_pandas_row_sink_get_rows() -> None:
    row_sink = PandasRowSink()
    row_sink.write_row({"id": 1, "name": "A"})

    assert row_sink.get_rows() == [{"id": 1, "name": "A"}]


def test_pandas_column_sink_write_batch_initializes_columns() -> None:
    col_sink = PandasColumnSink()
    col_sink.write_batch([{"id": 1, "name": "A"}])

    assert col_sink.get_columns()["id"][0] == 1
    assert col_sink.get_columns()["name"][0] == "A"


def test_pandas_sinks_context_and_columns() -> None:
    with PandasRowSink(field_names=["id"]) as row_sink:
        row_sink.write_row({"id": 1, "extra": 2})

    df = row_sink.to_dataframe()
    assert list(df.columns) == ["id"]

    with PandasColumnSink() as col_sink:
        col_sink.set_row_ids([1])
        col_sink.write_column("id", {1: 1})
        col_sink.write_columns({"name": {1: "Alice"}})
        col_sink.write_batch([{"id": 2, "name": "Bob"}])

    assert col_sink.get_row_ids() == [1, 0]
    assert col_sink.get_columns()["id"][0] == 2


def test_block_column_csv_sink_additional_paths(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "block.csv"

    def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(time, "sleep", _no_sleep)

    sink = BlockColumnCSVSink(str(output_path), ["id", "name"], col_width=8, write_delay=0.1)
    sink.set_row_ids([1])
    sink.write_column("id", {1: 1})

    sink.set_row_ids([2])
    sink.write_columns({"name": {2: "B"}})
    sink.write_column("unknown", {2: "X"})

    sink.write_batch([{"id": 3, "name": "C"}])
    sink.close()
    sink.close()

    assert output_path.exists()


def test_block_column_csv_sink_emits_warning(tmp_path: Path, caplog) -> None:
    output_path = tmp_path / "block_warning.csv"
    caplog.set_level(logging.WARNING, logger="scalim.sinks.sink_csv")

    _ = BlockColumnCSVSink(str(output_path), ["id"], col_width=6, write_delay=0.0)

    assert any("BlockColumnCSVSink" in record.message for record in caplog.records)


def test_block_column_csv_sink_internal_branches(tmp_path: Path) -> None:
    output_path = tmp_path / "block_ctx.csv"
    with BlockColumnCSVSink(str(output_path), ["id"], col_width=6, write_delay=0.0) as sink:
        sink.set_row_ids([1])

    sink2 = BlockColumnCSVSink(str(tmp_path / "block_none.csv"), ["id"], col_width=6, write_delay=0.0)
    sink2._initialized = True
    sink2._file = None
    sink2.set_row_ids([1])
    sink2.write_column("id", {1: 1})
    sink2._write_cell(0, 0, None)

    sink3 = BlockColumnCSVSink(str(tmp_path / "block_value.csv"), ["id"], col_width=6, write_delay=0.0)
    sink3.set_row_ids([1])
    sink3._write_cell(0, 0, None)
    sink3._init_file()
    sink3.close()


def test_column_csv_sink_close_exception_cleans_temp_file(tmp_path: Path, monkeypatch) -> None:
    import scalim.sinks._internal.sink_csv as csv_mod

    output_path = tmp_path / "cols_exc.csv"
    sink = ColumnCSVSink(str(output_path), ["id"])
    sink.set_row_ids([1])
    sink.write_column("id", {1: 1})

    original_open = csv_mod.io.open

    def _failing_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if ".csv.tmp" in str(path):
            raise OSError("simulated write failure")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(csv_mod.io, "open", _failing_open)

    with pytest.raises(OSError, match="simulated write failure"):
        sink.close()


def test_csv_sink_close_replace_exception_cleans_temp_file(tmp_path: Path, monkeypatch) -> None:
    import scalim.sinks._internal.sink_csv as csv_mod

    output_path = tmp_path / "rows_replace_exc.csv"
    sink = CSVSink(str(output_path), field_names=["id"])
    sink.write_row({"id": 1})
    temp_path = Path(sink._temp_path)
    assert temp_path.exists()

    def _failing_replace(_self: Path, _target: str) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(csv_mod.Path, "replace", _failing_replace)

    with pytest.raises(OSError, match="CSVSink close failed") as exc_info:
        sink.close()

    assert isinstance(exc_info.value.__cause__, OSError)
    assert "simulated replace failure" in str(exc_info.value.__cause__)
    assert str(output_path) in str(exc_info.value)
    assert not temp_path.exists()


def test_csv_sink_close_replace_exception_unlink_failure_logs_warning(tmp_path: Path, monkeypatch, caplog) -> None:
    import scalim.sinks._internal.sink_csv as csv_mod

    output_path = tmp_path / "rows_unlink_exc.csv"
    sink = CSVSink(str(output_path), field_names=["id"])
    sink.write_row({"id": 1})
    temp_path = Path(sink._temp_path)
    assert temp_path.exists()

    caplog.set_level(logging.WARNING, logger="scalim.sinks.sink_csv")

    def _failing_replace(_self: Path, _target: str) -> None:
        raise OSError("simulated replace failure")

    def _failing_unlink(_self: Path) -> None:
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(csv_mod.Path, "replace", _failing_replace)
    monkeypatch.setattr(csv_mod.Path, "unlink", _failing_unlink)

    with pytest.raises(OSError, match="CSVSink close failed"):
        sink.close()

    assert any(CSV_SINK_REMOVE_TEMP_FILE_FAILED in record.getMessage() for record in caplog.records)
    assert temp_path.exists()


def test_column_csv_sink_close_replace_exception_unlink_failure_logs_warning(tmp_path: Path, monkeypatch, caplog) -> None:
    import scalim.sinks._internal.sink_csv as csv_mod

    output_path = tmp_path / "cols_unlink_exc.csv"
    sink = ColumnCSVSink(str(output_path), ["id"])
    sink.set_row_ids([1])
    sink.write_column("id", {1: 1})

    caplog.set_level(logging.WARNING, logger="scalim.sinks.sink_csv")

    def _failing_replace(_self: Path, _target: str) -> None:
        raise OSError("simulated replace failure")

    def _failing_unlink(_self: Path) -> None:
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(csv_mod.Path, "replace", _failing_replace)
    monkeypatch.setattr(csv_mod.Path, "unlink", _failing_unlink)

    with pytest.raises(OSError, match="simulated replace failure"):
        sink.close()

    assert any(COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED in record.getMessage() for record in caplog.records)
