"""`sinks` 包.

该包提供执行/运行时层使用的输出端(`sink`).

实现细节位于 `scalim.sinks._internal` (非公共契约).
"""

# pragma: scalim-public-api tier1:120:scalim.sinks|sink 契约与常用 sinks|使用内置 sinks / 实现自定义 sink
# pragma: scalim-public-api tier1:130:scalim.sinks.rows|workflow typed rows artifact 稳定入口|`InMemoryRows` 中间态 / 转换与适配

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
    InMemoryColumnSink,
    InMemoryCsv,
    InMemoryCsvSink,
    InMemoryListSink,
    InMemoryRowSink,
    IRowSink,
    ISink,
    PandasColumnSink,
    PandasRowSink,
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
