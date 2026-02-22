# region imports

from collections.abc import Hashable, Mapping, Sequence
from typing import TYPE_CHECKING

from ..vendor.compact.importlibx import require_optional_dependency

if TYPE_CHECKING:
    import pandas as pd
else:
    pd = require_optional_dependency("pandas", context="scalim.sinks.sink_pandas")

from ..typedefs import FieldValue, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import Self, override
from .sink_base import IColumnSink, IRowSink

if TYPE_CHECKING:
    import types

# endregion


class PandasRowSink(IRowSink):
    field_names: list[str]
    _rows: list[RowData]
    _closed: bool

    def __init__(self, field_names: list[str] | None = None) -> None:
        self.field_names = field_names if field_names is not None else []
        self._rows = []
        self._closed = False

    @override
    def write_row(self, row: RowData) -> None:
        self._rows.append(dict(row))
        if not self.field_names:
            for key in row:
                if key not in self.field_names:
                    self.field_names.append(key)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            self.write_row(row)

    @override
    def close(self) -> None:
        self._closed = True

    def to_dataframe(self) -> "pd.DataFrame":
        if self.field_names:
            return pd.DataFrame(self._rows, columns=pd.Index(self.field_names))
        return pd.DataFrame(self._rows)

    def get_rows(self) -> list[RowData]:
        return self._rows

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "types.TracebackType | None",  # noqa: PYI036
    ) -> None:
        self.close()


class PandasColumnSink(IColumnSink):
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

    def to_dataframe(self) -> "pd.DataFrame":
        if not self._row_ids:
            return pd.DataFrame(columns=pd.Index(self.field_names or []))

        fields = self.field_names or list(self._columns.keys())
        data: dict[str, list[FieldValue | None]] = {}

        for field_key in fields:
            col_data = self._columns.get(field_key, {})
            data[field_key] = [col_data.get(pk) for pk in self._row_ids]

        return pd.DataFrame(data, columns=pd.Index(fields))

    def get_columns(self) -> dict[str, dict[Hashable, FieldValue]]:
        return self._columns

    def get_row_ids(self) -> list[Hashable]:
        return self._row_ids

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
    "PandasColumnSink",
    "PandasRowSink",
]
