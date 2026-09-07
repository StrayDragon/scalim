"""`InMemoryRows` 的内存中间态(用于 `workflow-intermediate-store`).

说明:
- `InMemoryRows` 与 `InMemoryCsv` 独立:前者保留任意 `Python` 细胞对象,后者为 `CSV` 等价的字符串化语义.
- `InMemoryRowsSink` 用于从 `RowData` 行流捕获 `InMemoryRows`(按 `field_id` 顺序).
- 细胞类型门禁不在 `ROWS`;写出兼容由 `sink` `accept set` / `opt-in` 预检 / 库边界负责.
- 运行时需兼容 `Python 3.6`.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from typing_extensions import override

from ...typedefs import CellValue, RowData
from .base import BaseRowSink
from .sink_csv import InMemoryCsv


@dataclass(frozen=True)
class InMemoryRows:
    """表格中间态的稳定表结构.

    - `header`: 字段 `field_id` 序列(顺序 `SSOT`)
    - `rows`: 行数据(细胞为任意 `object`;每行长度必须与 `header` 等长,列序一致)
    """

    header: list[str]
    rows: list[list[CellValue]]

    def __post_init__(self) -> None:
        msg: str
        for idx, field_id in enumerate(self.header):
            if not isinstance(field_id, str) or not field_id.strip():
                msg = f"InMemoryRows.header[{idx}] must be a non-empty string"
                raise ValueError(msg)

        width = len(self.header)
        for row_idx, row in enumerate(self.rows):
            if len(row) != width:
                msg = f"InMemoryRows.rows[{row_idx}] length mismatch: {len(row)} != {width}"
                raise ValueError(msg)

    def iter_row_data(self) -> Iterator[RowData]:
        header = list(self.header)
        for row in self.rows:
            yield dict(zip(header, row, strict=False))


class InMemoryRowsSink(BaseRowSink):
    """将行流写入 `InMemoryRows` 的内存 `sink`."""

    field_ids: list[str]
    _artifact: InMemoryRows
    _closed: bool

    def __init__(self, *, field_ids: Sequence[str] | None) -> None:
        if field_ids is None:
            msg = "必须提供 field_ids 参数"
            raise ValueError(msg)
        self.field_ids = list(field_ids)
        self._artifact = InMemoryRows(header=list(self.field_ids), rows=[])
        self._closed = False

    def to_artifact(self) -> InMemoryRows:
        return self._artifact

    def _format_row(self, row: RowData) -> list[CellValue]:
        values: list[CellValue] = []
        for field_id in self.field_ids:
            values.append(row.get(field_id))
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

    @override
    def discard(self) -> None:
        """失败路径:丢弃已捕获行,`MUST NOT` 当作成功产物."""
        if self._closed:
            return
        self._artifact = InMemoryRows(header=list(self.field_ids), rows=[])
        self._closed = True


def in_memory_rows_to_in_memory_csv(artifact: InMemoryRows) -> InMemoryCsv:
    """显式转换 `InMemoryRows` -> `InMemoryCsv`(保序 + 值规范化)."""

    def _normalize(value: CellValue) -> str:
        return "" if value is None else str(value)

    header = list(artifact.header)
    rows: list[list[str]] = []
    for row in artifact.rows:
        rows.append([_normalize(v) for v in row])
    return InMemoryCsv(header=header, rows=rows)


def iter_in_memory_rows_as_main_rows(artifact: InMemoryRows) -> Iterable[RowData]:
    """将 `InMemoryRows` 适配为 `engine.run(main_rows=...)` 可消费的行流."""

    class _Iterable:
        _header: list[str]
        _rows: list[list[CellValue]]

        def __init__(self, header: list[str], rows: list[list[CellValue]]) -> None:
            self._header = header
            self._rows = rows

        def __iter__(self) -> Iterator[RowData]:
            header = self._header
            for row in self._rows:
                yield dict(zip(header, row, strict=False))

    return _Iterable(header=list(artifact.header), rows=artifact.rows)


__all__ = ()
