"""`typed rows` 的内存中间态(用于 `workflow-intermediate-store`).

说明:
- `InMemoryRows` 与 `InMemoryCsv` 独立: 前者保留 `FieldValue` 类型域,后者为 `CSV` 等价的字符串化语义.
- `InMemoryRowsSink` 用于从 `RowData` 行流捕获 `InMemoryRows`(按 `field_id` 顺序).
- 运行时需兼容 `Python 3.6`.
"""

from decimal import Decimal
from typing import Iterable, Iterator, List, Optional, Sequence

from ...typedefs import FieldValue, RowData
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from .base import BaseRowSink
from .sink_csv import InMemoryCsv

_FIELD_VALUE_TYPES = (int, float, Decimal, str, bool)


def _is_field_value(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, _FIELD_VALUE_TYPES)


@dataclass(frozen=True)
class InMemoryRows:
    """`typed rows` 的稳定表结构.

    - `header`: 字段 `field_id` 序列(顺序 `SSOT`)
    - `rows`: 行数据(值域为 `FieldValue`;每行长度必须与 `header` 等长,列序一致)
    """

    header: List[str]
    rows: List[List[FieldValue]]

    def __post_init__(self) -> None:
        msg: str
        for idx, field_id in enumerate(self.header):
            if not isinstance(field_id, str) or not field_id.strip():
                msg = "InMemoryRows.header[{}] must be a non-empty string".format(idx)
                raise ValueError(msg)

        width = len(self.header)
        for row_idx, row in enumerate(self.rows):
            if len(row) != width:
                msg = "InMemoryRows.rows[{}] length mismatch: {} != {}".format(row_idx, len(row), width)
                raise ValueError(msg)
            for col_idx, value in enumerate(row):
                if not _is_field_value(value):
                    msg = "InMemoryRows.rows[{}][{}] must be a FieldValue".format(row_idx, col_idx)
                    raise TypeError(msg)

    def iter_row_data(self) -> Iterator[RowData]:
        header = list(self.header)
        for row in self.rows:
            yield dict(zip(header, row))


class InMemoryRowsSink(BaseRowSink):
    """将行流写入 `InMemoryRows` 的内存 `sink`."""

    field_ids: List[str]
    _artifact: InMemoryRows
    _closed: bool

    def __init__(self, *, field_ids: Optional[Sequence[str]]) -> None:
        if field_ids is None:
            msg = "必须提供 field_ids 参数"
            raise ValueError(msg)
        self.field_ids = list(field_ids)
        self._artifact = InMemoryRows(header=list(self.field_ids), rows=[])
        self._closed = False

    def to_artifact(self) -> InMemoryRows:
        return self._artifact

    def _format_row(self, row: RowData) -> List[FieldValue]:
        values: List[FieldValue] = []
        for field_id in self.field_ids:
            value = row.get(field_id)
            if not _is_field_value(value):
                msg = "InMemoryRowsSink received non-FieldValue: field_id={!r}, type={!r}".format(
                    str(field_id),
                    type(value).__name__,
                )
                raise TypeError(msg)
            values.append(value)
        return values

    @override
    def write_row(self, row: RowData) -> None:
        self._artifact.rows.append(self._format_row(row))

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            self._artifact.rows.append(self._format_row(row))

    @override
    def close(self) -> None:
        self._closed = True


def in_memory_rows_to_in_memory_csv(artifact: InMemoryRows) -> InMemoryCsv:
    """显式转换 `InMemoryRows` -> `InMemoryCsv`(保序 + 值规范化)."""

    def _normalize(value: FieldValue) -> str:
        return "" if value is None else str(value)

    header = list(artifact.header)
    rows: List[List[str]] = []
    for row in artifact.rows:
        rows.append([_normalize(v) for v in row])
    return InMemoryCsv(header=header, rows=rows)


def iter_in_memory_rows_as_main_rows(artifact: InMemoryRows) -> Iterable[RowData]:
    """将 `InMemoryRows` 适配为 `engine.run(main_rows=...)` 可消费的行流."""

    class _Iterable:
        _header: List[str]
        _rows: List[List[FieldValue]]

        def __init__(self, header: List[str], rows: List[List[FieldValue]]) -> None:
            self._header = header
            self._rows = rows

        def __iter__(self) -> Iterator[RowData]:
            header = self._header
            for row in self._rows:
                yield dict(zip(header, row))

    return _Iterable(header=list(artifact.header), rows=artifact.rows)


__all__ = []
