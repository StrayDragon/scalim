## MODIFIED Requirements

### Requirement: stable public entrypoints MUST be explicitly cataloged

系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让“当前能 import 的路径”自然演化成公共契约。

该目录在本轮至少 MUST 覆盖：

- `scalim.dsl.yaml_dsl` 及其官方 facade 符号（包括 `run`、`compile`、`run_workflow` 与运行期契约类型）
- `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.yaml_dsl.workflow_paths`
- `scalim.dsl.yaml_dsl.tools`
- `scalim.spec.ir`
- `scalim.workflow.loaders`（workflow YAML 中可通过字符串引用的内置 loader 入口）
- `scalim.events`（事件 envelope、事件类型常量与事件目录查询入口；typed payload 不作为公共导入契约）
- `scalim.sinks`（sink 契约与常用 sinks；内部 helper 不作为公共导入契约）

系统 MUST 将未列入目录的路径视为非公共契约；其中至少包括：

- `scalim.dsl.yaml_dsl.runtime.*`
- `scalim.dsl.yaml_dsl._internal.*`
- `scalim.dsl.yaml_dsl.schema_dsl.*`
- `scalim.dsl.by_yaml.*`（旧路径：本轮收敛后不得再作为用户侧稳定契约）
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
- **AND** 不得把 `scalim.dsl.yaml_dsl.runtime.*`、`scalim.dsl.yaml_dsl._internal.*` 或 `scalim.dsl.yaml_dsl.schema_dsl.*` 写成推荐用户路径
- **AND** 不得把旧的 `scalim.dsl.by_yaml.*` 写成推荐用户路径
- **AND** 不得把 `scalim.events._*` 或 `scalim.sinks._internal.*` 写成推荐用户路径
