# region imports

from collections.abc import Hashable, Mapping, Sequence
from typing import TYPE_CHECKING

from ..typedefs import FieldValue, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import Self, override
from .sink_base import BaseRowSink, IColumnSink

if TYPE_CHECKING:
    import types

# endregion


class InMemoryRowSink(BaseRowSink):
    """内存行式 Sink - 支持行级流式写入并存储在内存中 (FR023).

    主要用于测试和调试.

    示例::

        sink = InMemoryRowSink()
        sink.write_row({"id": 1, "name": "Alice"})
        sink.write_batch([{"id": 2, "name": "Bob"}])
        data = sink.get_data()
    """

    def __init__(self) -> None:
        self._data: list[RowData] = []
        self._closed: bool = False

    @override
    def write_row(self, row: RowData) -> None:
        self._data.append(dict(row))

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            self._data.append(dict(row))

    @override
    def close(self) -> None:
        self._closed = True

    def get_data(self) -> list[RowData]:
        return self._data


InMemoryListSink = InMemoryRowSink


class InMemoryColumnSink(IColumnSink):
    """内存列式 Sink - 支持按列追加写入并存储在内存中 (FR023).

    主要用于测试、调试和需要在内存中进一步处理数据的场景.

    数据访问方式:
    - get_columns(): 获取列式数据 (Dict[field_key, Dict[pk, value]])
    - get_rows(): 获取行式数据 (List[Dict[field_key, value]])
    - get_2d_list(): 获取二维列表 (List[List[value]])
    - get_column(field_key): 获取单列数据

    示例::

        sink = InMemoryColumnSink(["order_id", "name"])
        sink.set_row_ids([1, 2, 3])
        sink.write_column("order_id", {1: 1, 2: 2, 3: 3})
        sink.write_column("name", {1: "A", 2: "B", 3: "C"})
        sink.close()

        columns = sink.get_columns()
        rows = sink.get_rows()
    """

    field_names: list[str]
    _row_ids: list[Hashable]
    _columns: dict[str, dict[Hashable, FieldValue]]
    _closed: bool
    _auto_field_names: bool

    def __init__(self, field_names: list[str] | None = None) -> None:
        self._auto_field_names = field_names is None
        self.field_names = field_names if field_names is not None else []
        self._row_ids = []
        self._columns = {}
        self._closed = False

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        self._row_ids.extend(row_ids)

    @override
    def write_column(self, field_key: str, values: Mapping[Hashable, FieldValue]) -> None:
        if field_key not in self._columns:
            self._columns[field_key] = {}
        self._columns[field_key].update(values)
        if self._auto_field_names and field_key not in self.field_names:
            self.field_names.append(field_key)

    @override
    def write_columns(self, columns: Mapping[str, Mapping[Hashable, FieldValue]]) -> None:
        for field_key, values in columns.items():
            self.write_column(field_key, values)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row_idx, row in enumerate(rows):
            pk = row_idx
            if pk not in self._row_ids:
                self._row_ids.append(pk)
            for field_key, value in row.items():
                if field_key not in self._columns:
                    self._columns[field_key] = {}
                self._columns[field_key][pk] = value

    @override
    def close(self) -> None:
        self._closed = True

    # ============================================================
    # 数据访问方法
    # ============================================================

    def get_columns(self) -> dict[str, dict[Hashable, FieldValue]]:
        return self._columns

    def get_column(self, field_key: str) -> dict[Hashable, FieldValue]:
        return self._columns.get(field_key, {})

    def get_rows(self) -> list[RowData]:
        rows: list[RowData] = []
        for pk in self._row_ids:
            row: dict[str, FieldValue] = {}
            for field_key in self._columns:
                if pk in self._columns[field_key]:
                    row[field_key] = self._columns[field_key][pk]
            rows.append(row)
        return rows

    def get_2d_list(
        self,
        *,
        include_header: bool = False,
    ) -> list[list[str | FieldValue]]:
        result: list[list[str | FieldValue]] = []
        fields = self.field_names or list(self._columns.keys())

        if include_header:
            result.append(list(fields))

        for pk in self._row_ids:
            row_values: list[str | FieldValue] = []
            for field_key in fields:
                column_data = self._columns.get(field_key, {})
                row_values.append(column_data.get(pk))
            result.append(row_values)

        return result

    def get_row_ids(self) -> list[Hashable]:
        return self._row_ids

    def get_field_names(self) -> list[str]:
        return self.field_names or list(self._columns.keys())

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "types.TracebackType | None",  # noqa: PYI036
    ) -> None:
        self.close()


__all__ = [
    "InMemoryColumnSink",
    "InMemoryListSink",
    "InMemoryRowSink",
]
