## MODIFIED Requirements

### Requirement: stable public entrypoints MUST be explicitly cataloged

系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让“当前能 import 的路径”自然演化成公共契约。

该目录在本轮至少 MUST 覆盖：

- `scalim.dsl.by_yaml` 及其官方 facade 符号（包括 `run`、`compile`、`run_workflow` 与运行期契约类型）
- `scalim.dsl.by_yaml.workflow`
- `scalim.dsl.by_yaml.workflow_types`
- `scalim.dsl.by_yaml.workflow_paths`
- `scalim.spec.ir`
- `scalim.workflow.loaders`（workflow YAML 中可通过字符串引用的内置 loader 入口）
- `scalim.events`（事件 envelope、事件类型常量与事件目录查询入口；typed payload 不作为公共导入契约）
- `scalim.sinks`（sink 契约与常用 sinks；内部 helper 不作为公共导入契约）

系统 MUST 将未列入目录的路径视为非公共契约；其中至少包括：

- `scalim.dsl.by_yaml.runtime.*`（例如 `scalim.dsl.by_yaml.runtime.workflow_loaders`）
- `scalim.dsl.by_yaml.config_parsing.*`
- `scalim.dsl.by_yaml.schema_dsl.*`
- `scalim.events._*`
- `scalim.sinks._internal.*`

#### Scenario: curated public entrypoints are import-smoke covered
- **WHEN** 维护者执行 public-surface import smoke gate
- **THEN** 目录中的稳定公开入口 MUST 全部可导入
- **AND** gate MUST 以显式白名单为准,而不是扫描整个包树自动放大公共表面

### Requirement: public-facing materials MUST use only cataloged entrypoints

系统 MUST 要求文档、skills、examples 与 public API 回归用例仅使用已编目的稳定公开入口表达官方用法。

系统 MUST NOT 在这些面向用户的材料中把内部实现路径当作推荐导入路径、教程示例或长期契约。

#### Scenario: docs and examples avoid internal implementation imports
- **WHEN** 维护者审阅或检查用户可见文档、skills 与 examples
- **THEN** 其中的官方导入示例 MUST 仅引用已编目的稳定公开入口
- **AND** 不得把 `scalim.dsl.by_yaml.runtime.*`、`scalim.dsl.by_yaml.config_parsing.*` 或 `scalim.dsl.by_yaml.schema_dsl.*` 写成推荐用户路径
- **AND** 不得把 `scalim.events._*` 或 `scalim.sinks._internal.*` 写成推荐用户路径

## ADDED Requirements

### Requirement: events/sinks public facades MUST be pinned by explicit __all__ gates

系统 MUST 将 `scalim.events` 与 `scalim.sinks` 视为稳定公开入口的一部分，并通过显式 `__all__` 白名单回归门禁固定其公共导出面。

#### Scenario: changing facade exports fails fast in curated gate
- **WHEN** 维护者在 `scalim.events` 或 `scalim.sinks` 调整对外导出符号集合
- **THEN** curated public surface gate MUST fail-fast 指出缺失或新增的导出符号

