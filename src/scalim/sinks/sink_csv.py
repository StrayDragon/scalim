# region imports

import csv
import io
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

from .._internal.loggingx import prefix
from ..typedefs import FieldValue, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import Self, override
from .sink_base import (
    BaseRowSink,
    ColumnBatch,
    ColumnData,
    ColumnValues,
    IColumnSink,
    create_temp_path,
    iter_row_values,
    store_rows_as_columns,
    update_column,
    update_columns,
)

if TYPE_CHECKING:
    import types

# endregion

_LOGGER = logging.getLogger(__name__)

_SINKS_PREFIX = prefix("sinks")

CSV_SINK_ATOMIC_REPLACE_FAILED = _SINKS_PREFIX + "`CSVSink` 原子替换失败"
CSV_SINK_ATOMIC_REPLACE_FAILED_LOG = CSV_SINK_ATOMIC_REPLACE_FAILED + ": %s"

CSV_SINK_REMOVE_TEMP_FILE_FAILED = _SINKS_PREFIX + "`CSVSink` 删除临时文件失败"
CSV_SINK_REMOVE_TEMP_FILE_FAILED_LOG = CSV_SINK_REMOVE_TEMP_FILE_FAILED + ": %s"

COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED = _SINKS_PREFIX + "ColumnCSVSink 删除临时文件失败"
COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED_LOG = COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED + ": %s"


def _normalize_csv_value(value: Any) -> str:
    return "" if value is None else str(value)


class CSVSink(BaseRowSink):
    """`CSV` 行写入器:支持流式写入.

    支持自定义分隔符与编码.
    实现 `IRowSink` 接口,支持单行流式写入以优化内存使用(FR023).

    写入时使用临时文件;在 `close()` 时原子替换到目标路径,避免输入输出异常导致产生不完整文件.

    参数:
        `output_path`: 输出文件路径
        `delimiter`: 分隔符,默认逗号
        `encoding`: 编码,默认 `utf-8`
        `field_names`: 字段标识列表,用于从行数据中取值
        `header_names`: 表头名称列表(可选),用于输出表头;默认等于 `field_names`
        `include_header`: 是否包含表头,默认 `True`
        `flush_policy`: 刷新策略,默认 `"every_n_rows"`
        `flush_every_rows`: 按行数刷新阈值(当 `flush_policy="every_n_rows"` 时生效)

    示例:
    ```python
    with CSVSink("report.csv", field_names=["id", "name"]) as sink:
        sink.write_row({"id": 1, "name": "张三"})
        sink.write_batch([{"id": 2, "name": "李四"}])

    # 使用不同的表头名称
    with CSVSink("report.csv", field_names=["id", "name"], header_names=["编号", "姓名"]) as sink:
        sink.write_row({"id": 1, "name": "张三"})
    ```
    """

    output_path: str
    delimiter: str
    encoding: str
    include_header: bool
    flush_policy: str
    flush_every_rows: int
    _rows_since_flush: int
    _closed: bool
    field_names: List[str]
    header_names: List[str]
    _file: io.TextIOWrapper
    _writer: Any
    _temp_path: str
    _open_fn: Callable[..., io.TextIOWrapper]
    _aligned_cache_field_keys: Optional[Tuple[str, ...]]
    _aligned_cache_indexes: Optional[List[Optional[int]]]

    def __init__(
        self,
        output_path: str,
        delimiter: str = ",",
        encoding: str = "utf-8",
        field_names: Union[List[str], None] = None,
        header_names: Union[List[str], None] = None,
        include_header: bool = True,  # noqa: FBT001, FBT002
        flush_policy: str = "every_n_rows",
        flush_every_rows: int = 1000,
        open_fn: Optional[Callable[..., io.TextIOWrapper]] = None,
    ) -> None:
        self.output_path = output_path
        self.delimiter = delimiter
        self.encoding = encoding
        self.include_header = include_header
        self.flush_policy = flush_policy
        self.flush_every_rows = flush_every_rows
        self._open_fn = open_fn or io.open
        self._rows_since_flush = 0
        self._closed = False

        if field_names is None:
            msg = "必须提供 field_names 参数"
            raise ValueError(msg)

        self.field_names = field_names
        self.header_names = header_names if header_names is not None else field_names

        if self.flush_policy not in ("always", "every_n_rows"):
            msg = "Unknown flush_policy: '{}'".format(self.flush_policy)
            raise ValueError(msg)
        if self.flush_policy == "every_n_rows" and self.flush_every_rows < 1:
            msg = "flush_every_rows must be >= 1"
            raise ValueError(msg)

        # 使用临时文件,确保在同一目录以支持原子重命名
        self._temp_path = create_temp_path(output_path, ".csv.tmp")

        self._file = self._open_fn(self._temp_path, "w", encoding=encoding, newline="")
        self._writer = csv.writer(self._file, delimiter=self.delimiter)
        if self.include_header:
            self._write_header()
        self._aligned_cache_field_keys = None
        self._aligned_cache_indexes = None

    def _write_header(self) -> None:
        self._writer.writerow(self.header_names)

    def _format_row(self, row: RowData) -> List[str]:
        return [_normalize_csv_value(row.get(field_name)) for field_name in self.field_names]

    def _maybe_flush(self, rows_written: int) -> None:
        if self.flush_policy == "always":
            self._file.flush()
            return
        if self.flush_policy == "every_n_rows":
            self._rows_since_flush += rows_written
            if self._rows_since_flush >= self.flush_every_rows:
                self._file.flush()
                self._rows_since_flush = self._rows_since_flush % self.flush_every_rows

    @override
    def write_row(self, row: RowData) -> None:
        self._writer.writerow(self._format_row(row))
        self._maybe_flush(1)

    def write_row_aligned(self, field_keys: Sequence[str], values: Sequence[FieldValue]) -> None:
        if len(field_keys) != len(values):
            msg = "`write_row_aligned` 长度不一致: field_keys={} values={}".format(len(field_keys), len(values))
            raise ValueError(msg)

        cache_keys = self._aligned_cache_field_keys
        field_keys_tuple = tuple(field_keys)
        if cache_keys != field_keys_tuple:
            index_by_key: Dict[str, int] = {key: i for i, key in enumerate(field_keys_tuple)}
            self._aligned_cache_field_keys = field_keys_tuple
            self._aligned_cache_indexes = [index_by_key.get(name) for name in self.field_names]

        indexes = self._aligned_cache_indexes or []
        row_values: List[str] = []
        for idx in indexes:
            if idx is None:
                row_values.append("")
            else:
                row_values.append(_normalize_csv_value(values[idx]))
        self._writer.writerow(row_values)
        self._maybe_flush(1)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            self._writer.writerow(self._format_row(row))
        self._maybe_flush(len(rows))

    @override
    def close(self) -> None:
        if self._closed:
            return

        self._file.close()
        temp_path_obj = Path(self._temp_path)
        try:
            # 原子重命名临时文件到目标路径
            _ = temp_path_obj.replace(self.output_path)
        except Exception as exc:
            _LOGGER.exception(CSV_SINK_ATOMIC_REPLACE_FAILED_LOG, self.output_path)
            if temp_path_obj.exists():
                try:
                    temp_path_obj.unlink()
                except OSError:
                    _LOGGER.warning(CSV_SINK_REMOVE_TEMP_FILE_FAILED_LOG, temp_path_obj, exc_info=True)
            msg = "CSVSink close failed: failed to replace temp file {} -> {}".format(temp_path_obj, self.output_path)
            raise OSError(msg) from exc

        self._closed = True


class ColumnCSVSink(IColumnSink):
    """列式 `CSV` 写入器:用于生产环境的高性能列式写入(FR023).

    工作原理:
    1. 在内存中按列缓存数据
    2. 在 `close()` 时一次性将所有数据写入 `CSV` 文件

    优点:
    - 性能高:仅一次文件写入
    - 调用方可在 `write_column()` 后立即释放该列的源数据
    - 适合宽表场景(200+ 列)

    参数:
        `output_path`: 输出文件路径
        `field_names`: 字段标识列表,用于从列数据中取值
        `header_names`: 表头名称列表(可选),用于输出表头;默认等于 `field_names`
        `delimiter`: 分隔符,默认逗号
        `encoding`: 编码,默认 `utf-8`
        `include_header`: 是否包含表头,默认 `True`

    示例:
    ```python
    with ColumnCSVSink("/tmp/report.csv", ["id", "name"]) as sink:
        sink.set_row_ids([1, 2, 3])
        sink.write_column("id", {1: 1, 2: 2, 3: 3})
        sink.write_column("name", {1: "甲", 2: "乙", 3: "丙"})

    # 使用不同的表头名称
    with ColumnCSVSink("/tmp/report.csv", ["id", "name"], header_names=["编号", "姓名"]) as sink:
        sink.set_row_ids([1, 2, 3])
        sink.write_column("id", {1: 1, 2: 2, 3: 3})
    ```
    """

    output_path: str
    field_names: List[str]
    header_names: List[str]
    delimiter: str
    encoding: str
    include_header: bool
    _row_ids: List[Any]
    _columns: ColumnData
    _closed: bool

    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        delimiter: str = ",",
        encoding: str = "utf-8",
        include_header: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        self.output_path = output_path
        self.field_names = field_names
        self.header_names = header_names if header_names is not None else field_names
        self.delimiter = delimiter
        self.encoding = encoding
        self.include_header = include_header
        self._row_ids = []
        self._columns = {}
        self._closed = False

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        self._row_ids.extend(row_ids)

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        update_column(self._columns, field_key, values)

    def write_column_aligned(self, field_key: str, row_ids: "SinkRowKeySeq", values: Sequence[FieldValue]) -> None:
        if len(row_ids) != len(values):
            msg = "`write_column_aligned` 长度不一致: row_ids={} values={}".format(len(row_ids), len(values))
            raise ValueError(msg)
        if field_key not in self._columns:
            self._columns[field_key] = {}
        col = self._columns[field_key]
        for row_id, value in zip(row_ids, values):
            col[row_id] = value

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        update_columns(self._columns, columns)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        start_index = len(self._row_ids)

        def _pk_factory(row_idx: int) -> int:
            return start_index + row_idx

        store_rows_as_columns(rows, self._row_ids, self._columns, _pk_factory)

    @override
    def close(self) -> None:
        if self._closed:
            return

        # 使用临时文件,确保在同一目录以支持原子重命名
        temp_path = create_temp_path(self.output_path, ".csv.tmp")
        temp_path_obj = Path(temp_path)

        try:
            with io.open(temp_path, "w", encoding=self.encoding, newline="") as f:
                writer = csv.writer(f, delimiter=self.delimiter)
                if self.include_header:
                    writer.writerow(self.header_names)

                for row_values in iter_row_values(self._row_ids, self.field_names, self._columns):
                    writer.writerow([_normalize_csv_value(value) for value in row_values])

            # 原子重命名临时文件到目标路径
            _ = temp_path_obj.replace(self.output_path)
        except Exception:
            # 清理临时文件
            if temp_path_obj.exists():
                try:
                    temp_path_obj.unlink()
                except OSError:
                    _LOGGER.warning(COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED_LOG, temp_path_obj, exc_info=True)
            raise

        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        self.close()


class BlockColumnCSVSink(IColumnSink):
    """块列写入 `CSV` 写入器:用于演示的实时列写入(FR023).

    与 `RealtimeColumnCSVSink` 的区别:
    - `RealtimeColumnCSVSink`:每次写入一列都会重写整个文件
    - `BlockColumnCSVSink`:预分配文件空间,每次写入一列时 `seek` 到对应位置直接写入

    工作原理:
    1. `set_row_ids()` 时预分配整个文件空间(固定宽度列)
    2. `write_column()` 时 `seek` 到每个单元格位置直接写入
    3. 写入后 `flush`,便于观察者实时看到列被填充

    文件示例(`col_width=12`):
    ```text
    order_id, name
    (1,)
    (2,)
    (3,)
    ```

    写入 `name` 列后:
    ```text
    order_id, name
    1, 张三
    2, 李四
    3, 王五
    ```

    示例:
    ```python
    with BlockColumnCSVSink("/tmp/demo.csv", ["id", "name"], col_width=16) as sink:
        sink.set_row_ids([1, 2, 3])  # 预分配空间
        sink.write_column("id", {1: 1, 2: 2, 3: 3})  # 定位并写入
        sink.write_column("name", {1: "甲", 2: "乙", 3: "丙"})  # 定位并写入
    ```

    限制:
    - 值会被截断到 `col_width - 1` 字节(保留分隔符/换行位置)
    - 必须在 `write_column()` 之前调用 `set_row_ids()`
    - 仅用于演示,生产环境请使用 `ColumnCSVSink`
    """

    output_path: str
    field_names: List[str]
    col_width: int
    delimiter: bytes
    encoding: str
    _row_ids: List[Any]
    _pk_to_index: Dict[Any, int]
    _field_to_col_index: Dict[str, int]
    _file: Optional[BinaryIO]
    _closed: bool
    _write_delay: float
    _row_length: int
    _header_length: int
    _initialized: bool

    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        col_width: int = 24,
        delimiter: str = ",",
        encoding: str = "utf-8",
        write_delay: float = 0.5,
    ) -> None:
        self.output_path = output_path
        self.field_names = field_names
        self.col_width = col_width
        self.delimiter = delimiter.encode(encoding)
        self.encoding = encoding
        self._row_ids = []
        self._pk_to_index = {}
        self._field_to_col_index = {name: i for i, name in enumerate(field_names)}
        self._file = None
        self._closed = False
        self._write_delay = write_delay
        self._initialized = False

        num_cols = len(field_names)
        self._row_length = num_cols * col_width + (num_cols - 1) + 1
        self._header_length = self._row_length
        _LOGGER.warning("%sBlockColumnCSVSink 仅用于演示,生产环境请使用 ColumnCSVSink.", _SINKS_PREFIX)

    def _init_file(self) -> None:
        if self._initialized:
            return

        self._file = io.open(self.output_path, "wb+")  # noqa: SIM115

        header_parts: List[bytes] = []
        for name in self.field_names:
            name_bytes = name.encode(self.encoding)
            padded = name_bytes[: self.col_width].ljust(self.col_width, b" ")
            header_parts.append(padded)
        header_line = self.delimiter.join(header_parts) + b"\n"
        _ = self._file.write(header_line)

        empty_cell = b" " * self.col_width
        empty_row = self.delimiter.join([empty_cell] * len(self.field_names)) + b"\n"
        for _pk in self._row_ids:
            _ = self._file.write(empty_row)

        self._file.flush()
        self._initialized = True

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        if self._initialized:
            if self._file is None:
                return
            start_index = len(self._row_ids)
            for pk in row_ids:
                self._row_ids.append(pk)
                self._pk_to_index[pk] = start_index
                start_index += 1

            empty_cell = b" " * self.col_width
            empty_row = self.delimiter.join([empty_cell] * len(self.field_names)) + b"\n"
            _ = self._file.seek(0, 2)
            for _pk in row_ids:
                _ = self._file.write(empty_row)
            self._file.flush()
        else:
            for i, pk in enumerate(row_ids):
                self._row_ids.append(pk)
                self._pk_to_index[pk] = i
            self._init_file()

    def _get_cell_offset(self, row_index: int, col_index: int) -> int:
        row_offset = self._header_length + row_index * self._row_length
        col_offset = col_index * (self.col_width + 1)
        return row_offset + col_offset

    def _write_cell(self, row_index: int, col_index: int, value: FieldValue) -> None:
        if self._file is None:
            return
        if value is None:
            value_str = ""
        else:
            value_str = str(value)

        value_bytes = value_str.encode(self.encoding)
        padded = value_bytes[: self.col_width].ljust(self.col_width, b" ")

        offset = self._get_cell_offset(row_index, col_index)
        _ = self._file.seek(offset)
        _ = self._file.write(padded)

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        if not self._initialized:
            msg = "必须先调用 set_row_ids"
            raise RuntimeError(msg)

        col_index = self._field_to_col_index.get(field_key)
        if col_index is None:
            return

        if self._file is None:
            return
        for pk, value in values.items():
            row_index = self._pk_to_index.get(pk)
            if row_index is not None:
                self._write_cell(row_index, col_index, value)

        self._file.flush()

        if self._write_delay > 0:
            time.sleep(self._write_delay)

    def write_column_aligned(self, field_key: str, row_ids: "SinkRowKeySeq", values: Sequence[FieldValue]) -> None:
        if len(row_ids) != len(values):
            msg = "`write_column_aligned` 长度不一致: row_ids={} values={}".format(len(row_ids), len(values))
            raise ValueError(msg)
        if not self._initialized:
            msg = "必须先调用 set_row_ids"
            raise RuntimeError(msg)

        col_index = self._field_to_col_index.get(field_key)
        if col_index is None or self._file is None:
            return

        for pk, value in zip(row_ids, values):
            row_index = self._pk_to_index.get(pk)
            if row_index is not None:
                self._write_cell(row_index, col_index, value)

        self._file.flush()

        if self._write_delay > 0:
            time.sleep(self._write_delay)

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        for field_key, values in columns.items():
            self.write_column(field_key, values)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            for field_key, value in row.items():
                col_index = self._field_to_col_index.get(field_key)
                if col_index is not None:
                    pk = len(self._row_ids)
                    self._row_ids.append(pk)
                    self._pk_to_index[pk] = len(self._row_ids) - 1
                    if self._initialized and self._file is not None:
                        empty_cell = b" " * self.col_width
                        empty_row = self.delimiter.join([empty_cell] * len(self.field_names)) + b"\n"
                        _ = self._file.seek(0, 2)
                        _ = self._file.write(empty_row)
                        self._write_cell(self._pk_to_index[pk], col_index, value)
        if self._initialized and self._file is not None:
            self._file.flush()

    @override
    def close(self) -> None:
        if self._closed:
            return
        if self._file is not None:
            self._file.close()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        self.close()


__all__ = [
    "BlockColumnCSVSink",
    "CSVSink",
    "ColumnCSVSink",
]
