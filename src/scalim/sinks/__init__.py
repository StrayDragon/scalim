"""`sinks` 包.

该包提供执行/运行时层使用的输出端(`sink`).

实现细节位于 `scalim.sinks._internal` (非公共契约).
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
