## ADDED Requirements

### Requirement: stable public entrypoints MUST be explicitly cataloged

系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让“当前能 import 的路径”自然演化成公共契约。

该目录在本轮至少 MUST 覆盖：

- `scalim.dsl.by_yaml` 及其官方 facade 符号（包括 `run`、`compile`、`run_workflow` 与运行期契约类型）
- `scalim.dsl.by_yaml.workflow`
- `scalim.dsl.by_yaml.workflow_types`
- `scalim.dsl.by_yaml.workflow_paths`
- `scalim.spec.ir`
- `scalim.workflow.loaders`（workflow YAML 中可通过字符串引用的内置 loader 入口）

系统 MUST 将未列入目录的路径视为非公共契约；其中至少包括：

- `scalim.dsl.by_yaml.runtime.*`（例如 `scalim.dsl.by_yaml.runtime.workflow_loaders`）
- `scalim.dsl.by_yaml.config_parsing.*`
- `scalim.dsl.by_yaml.schema_dsl.*`

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
- **AND** 不得把 `scalim.dsl.by_yaml.runtime.*`、`config_parsing.*` 或 `schema_dsl.*` 写成推荐用户路径

### Requirement: unsafe capabilities MUST NOT live on default public facades

系统 MUST 将“放宽安全边界”的能力与默认公共 facade 隔离。

若后续仍需保留不安全能力，系统 MUST 通过显式 `unsafe` 语义的专用入口、专用参数或等价强标识暴露；系统 MUST NOT 继续将其挂载在默认公共 facade 上，造成“官方推荐入口也可直接放宽边界”的印象。

#### Scenario: public API review rejects non-explicit unsafe escape hatches
- **WHEN** 维护者为默认公共 facade 新增一个会放宽安全边界的能力
- **THEN** 该能力 MUST 因缺少显式 `unsafe` 语义而被视为不符合公共表面治理约束
