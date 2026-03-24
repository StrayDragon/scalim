"""`scalim` 框架包.

此包刻意不在顶层做公共重导出聚合,以避免:
- 调用方误用内部实现路径导致后续重构成本放大
- 导入时成本上升与循环依赖风险
- 无意引入可选依赖(例如 `pandas`/`rich`/`openpyxl`/`jsonschema`)的导入副作用

对外推荐入口(优先使用):
- `scalim.dsl.by_yaml`: `YAML` `DSL` 官方入口
- `scalim.spec.ir`: `IR` 类型官方入口
- `scalim.planning`: 规划层入口
- `scalim.execution`: 执行层入口
- `scalim.ob`: 可观测性入口
"""

from . import _project_constants

__version__ = _project_constants.VERSION

__all__ = ("__version__",)
