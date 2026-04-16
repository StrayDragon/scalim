"""`sinks.pandas` 稳定导出面(可选依赖).

说明:
- 本模块提供稳定的门面(`facade`): `scalim.sinks.pandas`.
- 该子模块承载带可选依赖的 `sinks`(例如 `pandas`).
- 具体实现仍在 `scalim.sinks._internal.*` 维护,此处仅做显式白名单导出.
- 运行时需兼容 `Python 3.6`.
"""

from ._internal.pandas import PandasColumnSink, PandasRowSink

__all__ = (
    "PandasColumnSink",
    "PandasRowSink",
)
