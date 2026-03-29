"""`sinks` 稳定导出面.

说明:
- 对外稳定导入路径仍为 `scalim.sinks`
- 具体实现细节位于 `scalim.sinks._internal` (非公共契约)
"""

from ._internal.base import (
    BaseColumnSink,
    BaseRowSink,
    BaseSink,
    ColumnBatch,
    ColumnData,
    ColumnValues,
    IColumnSink,
    IRowSink,
    ISink,
)
from ._internal.excel import ColumnExcelSink, ExcelSink, ExcelWorkbookSink
from ._internal.memory import InMemoryColumnSink, InMemoryListSink, InMemoryRowSink
from ._internal.pandas import PandasColumnSink, PandasRowSink
from ._internal.sink_csv import (
    BlockColumnCSVSink,
    ColumnCSVSink,
    CSVSink,
    InMemoryCsv,
    InMemoryCsvSink,
)

__all__ = (
    "BaseColumnSink",
    "BaseRowSink",
    "BaseSink",
    "BlockColumnCSVSink",
    "CSVSink",
    "ColumnBatch",
    "ColumnCSVSink",
    "ColumnData",
    "ColumnExcelSink",
    "ColumnValues",
    "ExcelSink",
    "ExcelWorkbookSink",
    "IColumnSink",
    "IRowSink",
    "ISink",
    "InMemoryColumnSink",
    "InMemoryCsv",
    "InMemoryCsvSink",
    "InMemoryListSink",
    "InMemoryRowSink",
    "PandasColumnSink",
    "PandasRowSink",
)
