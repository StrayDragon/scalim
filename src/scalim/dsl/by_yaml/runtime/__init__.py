"""`YAML` `DSL` 的运行时适配器包.

对外推荐入口为 `scalim.dsl.by_yaml`.

此包刻意不在包根做符号重导出;请从子模块显式导入:
- 运行入口:`scalim.dsl.by_yaml.runtime.entrypoints`
- 覆盖/结果契约:`scalim.dsl.by_yaml.runtime.contracts`
- 自省工具:`scalim.dsl.by_yaml.runtime.introspection`
"""

__all__ = []
