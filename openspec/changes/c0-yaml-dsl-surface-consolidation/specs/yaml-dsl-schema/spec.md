# yaml-dsl-schema Delta Specification (c0-yaml-dsl-surface-consolidation)

## ADDED Requirements

### Requirement: numeric constraints MUST declare an explicit numeric type in JSON Schema

当 schema 中某字段使用了数值约束（例如 `minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum`）时，生成器 MUST 同时为该字段声明显式数值类型：
- `type: number` 或 `type: integer`

该约束适用于 demand 与 workflow 两套 schema（含所有 definitions）。

#### Scenario: generation fails fast on missing numeric type
- **WHEN** schema 生成器发现某字段包含 `minimum/maximum` 但缺失显式 `type:number|integer`
- **THEN** 生成 MUST fail-fast
- **AND** 报错 MUST 指出逻辑路径（例如 `retry.max_elapsed_seconds`）

### Requirement: system MUST provide vNext schema artifacts alongside v1

系统 MUST 在 `src/scalim/dsl/by_yaml/schema/` 下提供一套 vNext schema 生成物（与 v1 并行），用于渐进迁移与 LSP 精确提示。

命名约束：
- demand vNext: `demand.vnext.gen.json`
- workflow vNext: `workflow.vnext.gen.json`

#### Scenario: both v1 and vNext schema paths are discoverable
- **WHEN** 调用方需要配置编辑器或 CI 校验
- **THEN** 系统 MUST 能同时提供 v1 与 vNext schema 的可定位路径（例如通过 CLI `yaml-dsl schema path` 或等价 API）

