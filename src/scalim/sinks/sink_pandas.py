# region imports

from typing import TYPE_CHECKING, Any, Dict, Hashable, List, Mapping, Optional, Sequence, Type, Union

from ..vendor.compact.importlibx import require_optional_dependency

if TYPE_CHECKING:
    import pandas as pd

from ..typedefs import FieldValue, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import Self, override
from .sink_base import IColumnSink, IRowSink

if TYPE_CHECKING:
    import types

# endregion


def _get_pandas_module() -> Any:
    return require_optional_dependency("pandas", context="scalim.sinks.sink_pandas")


class PandasRowSink(IRowSink):
    field_names: List[str]
    _rows: List[RowData]
    _closed: bool

    def __init__(self, field_names: Optional[List[str]] = None) -> None:
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

    def write_row_aligned(self, field_keys: Sequence[str], values: Sequence[FieldValue]) -> None:
        if len(field_keys) != len(values):
            msg = "`write_row_aligned` 长度不一致: field_keys={} values={}".format(len(field_keys), len(values))
            raise ValueError(msg)
        self.write_row(dict(zip(field_keys, values)))

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            self.write_row(row)

    @override
    def close(self) -> None:
        self._closed = True

    def to_dataframe(self) -> "pd.DataFrame":
        pd_module = _get_pandas_module()
        if self.field_names:
            return pd_module.DataFrame(self._rows, columns=self.field_names)
        return pd_module.DataFrame(self._rows)

    def get_rows(self) -> List[RowData]:
        return self._rows

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        self.close()


class PandasColumnSink(IColumnSink):
    field_names: List[str]
    _row_ids: List[Hashable]
    _columns: Dict[str, Dict[Hashable, FieldValue]]
    _closed: bool
    _auto_field_names: bool

    def __init__(self, field_names: Optional[List[str]] = None) -> None:
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

    def write_column_aligned(self, field_key: str, row_ids: "SinkRowKeySeq", values: Sequence[FieldValue]) -> None:
        if len(row_ids) != len(values):
            msg = "`write_column_aligned` 长度不一致: row_ids={} values={}".format(len(row_ids), len(values))
            raise ValueError(msg)
        if field_key not in self._columns:
            self._columns[field_key] = {}
        col = self._columns[field_key]
        for row_id, value in zip(row_ids, values):
            col[row_id] = value
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
        pd_module = _get_pandas_module()
        if not self._row_ids:
            return pd_module.DataFrame(columns=self.field_names or [])

        fields = self.field_names or list(self._columns.keys())
        data: Dict[str, List[Union[FieldValue, None]]] = {}

        for field_key in fields:
            col_data = self._columns.get(field_key, {})
            data[field_key] = [col_data.get(pk) for pk in self._row_ids]

        return pd_module.DataFrame(data, columns=fields)

    def get_columns(self) -> Dict[str, Dict[Hashable, FieldValue]]:
        return self._columns

    def get_row_ids(self) -> List[Hashable]:
        return self._row_ids

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
    "PandasColumnSink",
    "PandasRowSink",
]
