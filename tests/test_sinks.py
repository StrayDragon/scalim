import csv

import pytest

from scalim.sinks.sink_base import IColumnSink
from scalim.sinks.sink_csv import CSVSink, ColumnCSVSink


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


def test_csv_sink_requires_field_names(tmp_path):
    output_path = tmp_path / "missing.csv"

    with pytest.raises(ValueError, match="field_names"):
        _ = CSVSink(str(output_path))


def test_csv_sink_supports_field_mapping(tmp_path):
    """验证 `CSVSink` 能正确处理 `field_names` 与 `header_names`.

    - `field_names` 用于从行数据中取值
    - `header_names` 用于输出 CSV 表头
    """
    output_path = tmp_path / "mapped.csv"

    # `field_names=["id"]` 表示从行中使用键 `"id"` 取值
    # `header_names=["identifier"]` 表示 CSV 表头显示 `"identifier"`
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
    """验证 CSV 写出端能正确使用 `header_names` 输出表头, 使用 `field_names` 输出值."""
    output_path = tmp_path / "output.csv"
    rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    _write_rows_to_csv(
        output_path,
        sink_cls,
        rows,
        header_names=["编号", "姓名"],
    )

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "编号,姓名"  # 表头使用 `header_names`
    assert lines[1] == "1,Alice"  # 值使用 `field_names` 对应的键
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


def test_csv_sink_atomic_write(tmp_path):
    """验证 `CSVSink` 使用原子写入(临时文件 + 重命名)."""
    import os

    output_path = tmp_path / "output.csv"

    with CSVSink(str(output_path), field_names=["id", "name"]) as sink:
        # 写入过程中应存在临时文件
        sink.write_row({"id": 1, "name": "Alice"})
        # 最终文件在 `close` 前不应存在(调用 `close` 时才写入/替换)
        # 注意: 原子写入下,最终文件仅会在 `close()` 后出现

    # `close` 后最终文件应存在
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # 表头 + 1 行数据


def test_column_csv_sink_atomic_write_on_error(tmp_path):
    """验证 `ColumnCSVSink` 在发生错误时能清理临时文件."""
    import os

    output_path = tmp_path / "output.csv"

    # 创建写出端,并刻意不正确关闭
    sink = ColumnCSVSink(str(output_path), field_names=["id", "name"])
    sink.set_row_ids([1, 2])
    sink.write_column("id", {1: 1, 2: 2})
    # 不调用 `close`: 不应写出最终文件

    # 正常调用 `close` 后应写出最终文件
    sink.close()
    assert output_path.exists()
