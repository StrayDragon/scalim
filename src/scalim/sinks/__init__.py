"""`sinks` 包.

该包提供执行/运行时层使用的输出端(`sink`).

实现细节位于 `scalim.sinks._internal` (非公共契约).
"""

# pragma: scalim-public-api tier1:120:scalim.sinks|sink 契约与常用 sinks|使用内置 sinks / 实现自定义 sink
# pragma: scalim-public-api tier1:121:scalim.sinks.memory|memory sinks(调试/测试/捕获)|`InMemoryRowDataSink`/`InMemoryCsv` 等
# pragma: scalim-public-api tier1:122:scalim.sinks.pandas|pandas sinks(可选依赖)|需要 `pandas` 时显式使用该子模块

from .api import (
    BaseColumnSink,
    BaseRowSink,
    BaseSink,
    BlockColumnCSVSink,
    ColumnBatch,
    ColumnCSVSink,
    ColumnData,
    ColumnExcelSink,
    ColumnValues,
    CSVSink,
    ExcelSink,
    ExcelWorkbookSink,
    IColumnSink,
    IRowSink,
    ISink,
    StreamingColumnExcelSink,
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
    "StreamingColumnExcelSink",
)
