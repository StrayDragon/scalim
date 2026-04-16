"""`sinks.memory` 稳定导出面.

说明:
- 本模块提供稳定的门面(`facade`): `scalim.sinks.memory`.
- 内存 `sinks` 主要用于调试/测试/捕获输出(例如拿到 `List[RowData]` 做二次处理).
- 具体实现仍在 `scalim.sinks._internal.*` 维护,此处仅做显式白名单导出.
- 运行时需兼容 `Python 3.6`.
"""

from ._internal.memory import InMemoryColumnSink, InMemoryRowDataSink
from ._internal.sink_csv import InMemoryCsv, InMemoryCsvSink

__all__ = (
    "InMemoryColumnSink",
    "InMemoryCsv",
    "InMemoryCsvSink",
    "InMemoryRowDataSink",
)
