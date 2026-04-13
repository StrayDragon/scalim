from pathlib import Path

import pytest

from scalim.sinks import BlockColumnCSVSink, CSVSink, ColumnCSVSink


def test_csv_sink_close_replace_exception_skips_unlink_when_temp_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.sinks._internal.sink_csv as csv_mod

    output_path = tmp_path / "rows_replace_missing_temp.csv"
    sink = CSVSink(str(output_path), field_names=["id"])
    sink.write_row({"id": 1})

    sink._file.close()  # noqa: SLF001
    temp_obj = Path(sink._temp_path)  # noqa: SLF001
    temp_obj.unlink()
    assert not temp_obj.exists()

    def _failing_replace(_temp_path: str, _output_path: str) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(csv_mod, "atomic_replace_temp_path", _failing_replace)

    with pytest.raises(OSError, match="CSVSink close failed"):
        sink.close()


def test_column_csv_sink_write_column_aligned_reuses_existing_column(tmp_path: Path) -> None:
    output_path = tmp_path / "cols_aligned.csv"
    sink = ColumnCSVSink(str(output_path), ["id"])
    sink.set_row_ids([1])
    sink.write_column("id", {1: 1})
    sink.write_column_aligned("id", [1], [2])
    sink.close()

    assert output_path.exists()


def test_column_csv_sink_close_missing_temp_path_skips_unlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scalim.sinks._internal.sink_csv as csv_mod

    output_path = tmp_path / "cols_missing_tmp.csv"
    sink = ColumnCSVSink(str(output_path), ["id"])
    sink.set_row_ids([1])
    sink.write_column("id", {1: 1})

    missing_temp_path = tmp_path / "missing-dir" / "nope.csv.tmp"
    monkeypatch.setattr(csv_mod, "create_temp_path", lambda _output, _suffix: str(missing_temp_path))

    with pytest.raises(OSError):
        sink.close()


def test_block_column_csv_sink_write_column_skips_unknown_row_ids(tmp_path: Path) -> None:
    output_path = tmp_path / "block_unknown_pk.csv"
    sink = BlockColumnCSVSink(str(output_path), ["id"], col_width=6, write_delay=0.0)
    sink.set_row_ids([1])
    sink.write_column("id", {2: 2, 1: 1})
    sink.close()

    assert output_path.exists()


def test_block_column_csv_sink_write_column_aligned_skips_unknown_row_ids(tmp_path: Path) -> None:
    output_path = tmp_path / "block_aligned_unknown_pk.csv"
    sink = BlockColumnCSVSink(str(output_path), ["id"], col_width=6, write_delay=0.0)
    sink.set_row_ids([1])
    sink.write_column_aligned("id", [2, 1], [2, 1])
    sink.close()

    assert output_path.exists()


def test_block_column_csv_sink_write_batch_before_init_skips_file_writes_and_flush(tmp_path: Path) -> None:
    output_path = tmp_path / "block_uninit.csv"
    sink = BlockColumnCSVSink(str(output_path), ["id"], col_width=6, write_delay=0.0)
    sink.write_batch([{"unknown": "X", "id": 1}])
    sink.close()

    assert not output_path.exists()

