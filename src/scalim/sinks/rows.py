"""`InMemoryRows` 的稳定公开导入路径.

说明:
- 本模块提供稳定的门面(`facade`): `scalim.sinks.rows`.
- 具体实现仍在 `scalim.sinks._internal.rows` 维护,此处仅做显式白名单导出.
- 运行时需兼容 `Python 3.6`.
"""

from ._internal.rows import (
    InMemoryRows,
    InMemoryRowsSink,
    in_memory_rows_to_in_memory_csv,
    iter_in_memory_rows_as_main_rows,
)

__all__ = (
    "InMemoryRows",
    "InMemoryRowsSink",
    "in_memory_rows_to_in_memory_csv",
    "iter_in_memory_rows_as_main_rows",
)
