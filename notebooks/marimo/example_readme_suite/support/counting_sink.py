"""Counting row sink：写入后丢弃行，只累计条数（用于内存对比的 scalim 侧）。"""

from __future__ import annotations

from typing import Sequence

from scalim.sinks import BaseRowSink
from scalim.typedefs import RowData
from scalim.vendor.compact.typing_extensionsx import override


class CountingRowSink(BaseRowSink):
    def __init__(self) -> None:
        self.rows_written = 0
        self._closed = False

    @override
    def write_row(self, row: RowData) -> None:
        self.rows_written += 1

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self.rows_written += len(rows)

    @override
    def close(self) -> None:
        self._closed = True
