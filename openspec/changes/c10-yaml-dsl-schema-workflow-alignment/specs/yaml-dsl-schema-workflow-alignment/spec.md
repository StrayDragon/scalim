## ADDED Requirements

### Requirement: workflow `resources` schema MUST expose only runtime-supported keys
workflow `resources` 的 schema 与静态校验面 MUST 以 runtime parser / compiler 实际支持的结构为准:

- `workflow.resources` MUST NOT 暴露 runtime 不支持的 keys
- `workflow.resources` MUST NOT 支持 imports expansion 或 `$import`
- 当用户写入被移除的旧 key 时,系统 MUST 提供可执行的 migration hint

#### Scenario: workflow resource import syntax is rejected before runtime
- **GIVEN** 某个 workflow YAML 在 `workflow.resources.books.<id>` 下写入 `$import`
- **WHEN** 用户执行 schema 校验或 workflow validate
- **THEN** 系统 MUST 将其识别为不受支持的结构
- **AND** MUST 给出迁移提示而不是等到更深层 runtime 才暴露漂移

### Requirement: generated numeric constraints MUST declare numeric types
凡是生成到 JSON Schema 的 numeric constraints,若使用了 `minimum`、`maximum`、`exclusiveMinimum` 或 `exclusiveMaximum`,对应 schema 节点 MUST 同时显式声明 `type: number` 或 `type: integer`。

#### Scenario: schema generation fails on a clearly invalid numeric constraint
- **WHEN** schema generation 遇到某个节点声明了 `minimum` 但未声明数值类型
- **THEN** 生成流程 MUST fail-fast
- **AND** 错误 MUST 指向具体的 schema DSL 定义位置或字段来源

### Requirement: schema/workflow drift gate MUST protect the highest-risk surfaces first
仓库 MUST 提供针对高风险 drift 的自动化 gate,至少覆盖:

- `workflow.resources` allowed keys 集合
- numeric constraints typing 完整性

#### Scenario: a drift regression is caught by the gate
- **WHEN** 某次改动让 workflow schema 暴露了 runtime 不支持的 key,或重新引入 numeric typing hole
- **THEN** 自动化 gate MUST 在提交前或 CI 中失败
- **AND** 不得依赖人工 review 才发现该类问题
