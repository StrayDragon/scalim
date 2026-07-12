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
from ._internal.sink_csv import (
    BlockColumnCSVSink,
    ColumnCSVSink,
    CSVSink,
)
from ._internal.streaming_column_excel import StreamingColumnExcelSink

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
    "StreamingColumnExcelSink",
)
