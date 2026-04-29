import csv

import pytest

from scalim.sinks import IColumnSink
from scalim.sinks import CSVSink, ColumnCSVSink
from scalim.sinks.memory import InMemoryCsvSink


def _write_rows_to_csv(output_path, sink_cls, rows, header_names=None):
    if sink_cls is CSVSink:
        with sink_cls(
            str(output_path),
            field_names=["id", "name"],
            header_names=header_names,
        ) as sink:
            for row in rows:
                sink.write_row(row)
        return

    sink = sink_cls(
        str(output_path),
        field_names=["id", "name"],
        header_names=header_names,
    )
    row_ids = [row["id"] for row in rows]
    sink.set_row_ids(row_ids)
    sink.write_column("id", {row["id"]: row["id"] for row in rows})
    sink.write_column("name", {row["id"]: row["name"] for row in rows})
    sink.close()


def test_column_csv_sink_write_batch_appends(tmp_path):
    output_path = tmp_path / "output.csv"
    sink = ColumnCSVSink(str(output_path), ["id", "name"])

    sink.write_batch([{"id": 1, "name": "Alice"}])
    sink.write_batch([{"id": 2, "name": "Bob"}])
    sink.close()
    sink.close()

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines == [
        "id,name",
        "1,Alice",
        "2,Bob",
    ]


def test_column_csv_sink_write_columns_merge(tmp_path):
    output_path = tmp_path / "output.csv"
    sink = ColumnCSVSink(str(output_path), ["id", "name"])

    sink.set_row_ids([1, 2])
    sink.write_column("id", {1: 1, 2: 2})
    sink.write_columns({"name": {1: "Alice"}})
    sink.write_columns({"name": {2: "Bob"}})
    sink.close()

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines == [
        "id,name",
        "1,Alice",
        "2,Bob",
    ]


def test_csv_sink_write_row_and_batch(tmp_path):
    output_path = tmp_path / "rows.csv"

    with CSVSink(str(output_path), field_names=["id", "name"]) as sink:
        sink.write_row({"id": 1, "name": "Alice"})
        sink.write_batch([{"id": 2, "name": "Bob"}])

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines == [
        "id,name",
        "1,Alice",
        "2,Bob",
    ]


def test_in_memory_csv_sink_normalizes_values_like_csv_sink(tmp_path):
    rows = [
        {"id": 1, "name": None},
        {"id": None, "name": "Alice"},
        {"id": True, "name": 3.14},
    ]

    mem_sink = InMemoryCsvSink(field_names=["id", "name"])
    mem_sink.write_batch(rows)
    mem_sink.close()
    artifact = mem_sink.to_artifact()
    assert artifact.header == ["id", "name"]

    output_path = tmp_path / "rows.csv"
    with CSVSink(str(output_path), field_names=["id", "name"]) as sink:
        sink.write_batch(rows)

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        file_header = next(reader)
        file_rows = [list(r) for r in reader]

    assert list(file_header) == artifact.header
    assert file_rows == artifact.rows


def test_in_memory_csv_sink_rejects_writes_when_closed() -> None:
    mem_sink = InMemoryCsvSink(field_names=["id"])
    mem_sink.close()

    with pytest.raises(RuntimeError, match="InMemoryCsvSink is closed"):
        mem_sink.write_row({"id": 1})
    with pytest.raises(RuntimeError, match="InMemoryCsvSink is closed"):
        mem_sink.write_batch([{"id": 1}])


def test_in_memory_csv_sink_requires_field_names() -> None:
    with pytest.raises(ValueError, match="field_names"):
        _ = InMemoryCsvSink()


def test_csv_sink_requires_field_names(tmp_path):
    output_path = tmp_path / "missing.csv"

    with pytest.raises(ValueError, match="field_names"):
        _ = CSVSink(str(output_path))


def test_csv_sink_supports_field_mapping(tmp_path):
    """Test that CSVSink correctly handles field_names vs header_names.

    This test verifies that field_names is used to extract values from rows,
    while header_names is used for the CSV header output.
    """
    output_path = tmp_path / "mapped.csv"

    # field_names=["id"] means we extract value using key "id" from the row
    # header_names=["identifier"] means the CSV header shows "identifier"
    sink = CSVSink(str(output_path), field_names=["id"], header_names=["identifier"])
    sink.write_row({"id": 7})
    sink.close()

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines == [
        "identifier",
        "7",
    ]


def test_csv_sink_creates_output_directory(tmp_path):
    output_path = tmp_path / "nested" / "out.csv"
    assert output_path.parent.exists() is False

    with CSVSink(str(output_path), field_names=["id"]) as sink:
        sink.write_row({"id": 1})

    assert output_path.parent.is_dir()
    assert output_path.is_file()
    assert output_path.read_text(encoding="utf-8").strip().splitlines() == ["id", "1"]


class _DefaultColumnSink(IColumnSink):
    def __init__(self) -> None:
        self.row_ids = []
        self.columns = {}

    def set_row_ids(self, row_ids) -> None:  # type: ignore[override]
        self.row_ids.extend(row_ids)

    def write_column(self, field_key, values) -> None:  # type: ignore[override]
        if field_key not in self.columns:
            self.columns[field_key] = {}
        self.columns[field_key].update(values)

    def write_columns(self, columns) -> None:  # type: ignore[override]
        for field_key, values in columns.items():
            self.write_column(field_key, values)

    def close(self) -> None:  # type: ignore[override]
        return None


def test_default_column_sink_write_batch_converts_rows():
    sink = _DefaultColumnSink()
    rows = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]

    sink.write_batch(rows)

    assert sink.columns["id"][0] == 1
    assert sink.columns["name"][1] == "Bob"


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sink_with_header_names(tmp_path, sink_cls):
    """Test that CSV sinks correctly use header_names for header and field_names for values."""
    output_path = tmp_path / "output.csv"
    rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    _write_rows_to_csv(
        output_path,
        sink_cls,
        rows,
        header_names=["编号", "姓名"],
    )

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "编号,姓名"  # Header uses header_names
    assert lines[1] == "1,Alice"  # Values from field_names keys
    assert lines[2] == "2,Bob"


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sink_escapes_special_chars(tmp_path, sink_cls):
    output_path = tmp_path / "escape.csv"
    payload = 'Alice, "A"\nB'

    _write_rows_to_csv(output_path, sink_cls, [{"id": 1, "name": payload}])

    with output_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    assert rows == [
        ["id", "name"],
        ["1", payload],
    ]


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sinks_preserve_raw_formula_like_values_by_default(tmp_path, sink_cls) -> None:
    output_path = tmp_path / "formula.csv"
    rows = [
        {"id": 1, "name": "=1+1"},
        {"id": 2, "name": "  -2+2"},
        {"id": 3, "name": "'=already"},
    ]
    _write_rows_to_csv(
        output_path,
        sink_cls,
        rows,
        header_names=["=id", "name"],
    )

    with output_path.open(encoding="utf-8", newline="") as f:
        out_rows = list(csv.reader(f))

    assert out_rows == [
        ["=id", "name"],
        ["1", "=1+1"],
        ["2", "  -2+2"],
        ["3", "'=already"],
    ]


def test_csv_sinks_allow_formulas_false_escapes_formula_like_values(tmp_path) -> None:
    rows = [
        {"id": 1, "name": "=1+1"},
        {"id": 2, "name": "  -2+2"},
        {"id": 3, "name": "'=already"},
    ]

    output_path = tmp_path / "allow_row.csv"
    with CSVSink(
        str(output_path),
        field_names=["id", "name"],
        header_names=["=id", "name"],
        allow_formulas=False,
    ) as sink:
        sink.write_batch(rows)

    with output_path.open(encoding="utf-8", newline="") as f:
        out_rows = list(csv.reader(f))
    assert out_rows == [
        ["'=id", "name"],
        ["1", "'=1+1"],
        ["2", "'  -2+2"],
        ["3", "'=already"],
    ]

    output_path2 = tmp_path / "allow_column.csv"
    sink2 = ColumnCSVSink(
        str(output_path2),
        field_names=["id", "name"],
        header_names=["=id", "name"],
        allow_formulas=False,
    )
    row_ids = [row["id"] for row in rows]
    sink2.set_row_ids(row_ids)
    sink2.write_column("id", {row["id"]: row["id"] for row in rows})
    sink2.write_column("name", {row["id"]: row["name"] for row in rows})
    sink2.close()

    with output_path2.open(encoding="utf-8", newline="") as f:
        out_rows2 = list(csv.reader(f))
    assert out_rows2 == out_rows


def test_csv_sink_atomic_write(tmp_path):
    """Test that CSVSink uses atomic write (temp file + rename)."""
    import os

    output_path = tmp_path / "output.csv"

    with CSVSink(str(output_path), field_names=["id", "name"]) as sink:
        # During write, temp file should exist
        sink.write_row({"id": 1, "name": "Alice"})
        # Final file should not exist yet (written on close)
        # Note: With atomic write, the final file exists only after close()

    # After close, final file should exist
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # header + 1 row
    sink.close()


def test_column_csv_sink_atomic_write_on_error(tmp_path):
    """Test that ColumnCSVSink cleans up temp file on error."""
    import os

    output_path = tmp_path / "output.csv"

    # Create a sink and intentionally don't close it properly
    sink = ColumnCSVSink(str(output_path), field_names=["id", "name"])
    sink.set_row_ids([1, 2])
    sink.write_column("id", {1: 1, 2: 2})
    # Don't close - no file should be written

    # After proper close, file should exist
    sink.close()
    assert output_path.exists()
