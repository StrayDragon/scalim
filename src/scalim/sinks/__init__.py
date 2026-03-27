"""`sinks` 包.

该包提供执行/运行时层使用的输出端(`sink`).

实现细节位于 `scalim.sinks._internal`.
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
    create_temp_path,
    iter_row_values,
    store_rows_as_columns,
    update_column,
    update_columns,
)
from ._internal.excel import ColumnExcelSink, ExcelSink, ExcelWorkbookSink
from ._internal.memory import InMemoryColumnSink, InMemoryListSink, InMemoryRowSink
from ._internal.pandas import PandasColumnSink, PandasRowSink
from ._internal.rows import (
    InMemoryRows,
    InMemoryRowsSink,
    in_memory_rows_to_in_memory_csv,
    iter_in_memory_rows_as_main_rows,
)
from ._internal.sink_csv import (
    COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED,
    CSV_SINK_REMOVE_TEMP_FILE_FAILED,
    BlockColumnCSVSink,
    ColumnCSVSink,
    CSVSink,
    InMemoryCsv,
    InMemoryCsvSink,
)

__all__ = (
    "COLUMN_CSV_SINK_REMOVE_TEMP_FILE_FAILED",
    "CSV_SINK_REMOVE_TEMP_FILE_FAILED",
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
    "InMemoryRows",
    "InMemoryRowsSink",
    "PandasColumnSink",
    "PandasRowSink",
    "create_temp_path",
    "in_memory_rows_to_in_memory_csv",
    "iter_in_memory_rows_as_main_rows",
    "iter_row_values",
    "store_rows_as_columns",
    "update_column",
    "update_columns",
)
