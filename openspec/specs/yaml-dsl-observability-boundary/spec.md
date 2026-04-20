# yaml-dsl-observability-boundary Specification

## Purpose
将 observability 配置从 YAML 主线移除，迁移到 Python/CLI runtime entrypoints，并在迁移期内提供可执行的迁移警告。

## Related Concepts
- observability.* YAML 字段（legacy）
- runtime entrypoints
- migration warnings
- custom hooks/observers
- docs/skills/notebooks/examples 迁移
## Requirements
### Requirement: YAML mainline MUST NOT treat `observability.*` as authoring surface
主线 YAML MUST 不再把 `observability.*` 作为稳定 authoring surface:

- demand / workflow schema MUST 从主线 YAML 中移除 `observability.*`
- 主线 parser / validator MUST 不再把 observability 视为业务建模字段

#### Scenario: new YAML authoring does not include observability blocks
- **WHEN** 用户编写新的 demand 或 workflow YAML
- **THEN** `observability.*` MUST NOT 作为推荐或受支持的主线路径出现

### Requirement: known legacy `observability.*` keys MUST provide actionable migration warnings during transition
在迁移期内,系统 MUST 对已知 legacy `observability.*` key 提供可执行的迁移 warning:

- warning MUST 明确该 key 将被忽略
- warning MUST 指向 Python / CLI runtime entrypoint 的迁移路径
- 普通未知字段 MUST 继续按现有 unknown-field 规则处理,不得一律降级为 warning

#### Scenario: legacy observability key emits a migration warning
- **GIVEN** 某个旧 YAML 仍包含已知的 `observability.logging` 或等价 key
- **WHEN** 用户执行 validate 或运行入口解析
- **THEN** 系统 MUST 发出 migration warning
- **AND** MUST 告知改用 Python / CLI runtime entrypoint

### Requirement: observability integration MUST be owned by runtime entrypoints
可观测性集成 MUST 由 Python / CLI runtime entrypoints 承载:

- runtime entrypoints MUST 能承载自定义 hooks / observers / viz 配置
- YAML 主线 MUST 不再重复建模这些 integration surfaces

#### Scenario: custom observer is attached without YAML observability config
- **WHEN** 用户需要挂接自定义 hook、observer 或内部观测工具
- **THEN** 系统 MUST 通过 Python / CLI runtime entrypoints 完成装配
- **AND** MUST NOT 依赖 YAML `observability.*`

### Requirement: docs, skills, notebooks and examples MUST migrate away from YAML observability authoring
仓库内面向用户的材料 MUST 不再把 YAML `observability.*` 作为推荐写法:

- docs MUST 以 runtime entrypoints 作为 SSOT
- skills / notebooks / examples MUST 同步迁移

#### Scenario: user-facing materials no longer teach YAML observability blocks
- **WHEN** 用户阅读仓库中的 YAML DSL 文档、skills 或 notebooks
- **THEN** 这些材料 MUST 不再把 `observability.*` 作为主线 authoring 示例
- **AND** MUST 给出 runtime entrypoints 的替代路径

