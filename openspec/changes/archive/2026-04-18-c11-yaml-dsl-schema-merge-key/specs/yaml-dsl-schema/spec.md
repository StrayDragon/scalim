# yaml-dsl-schema (delta) Specification

## ADDED Requirements

### Requirement: YAML DSL JSON Schemas MUST allow YAML merge key (`<<`) where propertyNames is used

系统 MUST 对齐 schema-only 校验与 runtime 的 YAML merge key 支持：

- 对 `demand.gen.json` / `workflow.gen.json` / `scalim_yaml.gen.json` 中任何使用 `propertyNames` 约束 mapping key 的 object 节点，生成的 schema MUST 显式允许 key 为 `<<`。
- 除 `<<` 之外，原有 `propertyNames` 规则 MUST 保持不变（不得放宽既有命名约束）。

说明：
- 该要求的目标是消除 editor/YAML Language Server 对 merge key 的假阳性，避免用户被迫关闭 schema 或放弃 `<<` 复用。
- runtime 仍是最终语义裁决与严格校验来源；schema-only 的放宽仅用于提升 authoring 体验。

#### Scenario: demand schema validation accepts merge key in map-like objects
- **GIVEN** 用户的 demand YAML 在 `fields`/`sources`/`imports` 等 mapping 节点使用 YAML merge key，例如：
  - `fields: {<<: *base_fields, field_c: {...}}`
- **WHEN** 编辑器使用生成的 `demand.gen.json` 做 schema-only 校验
- **THEN** MUST NOT 报告 `propertyNames` pattern mismatch for key `<<`

#### Scenario: workflow schema validation accepts merge key in init_vars
- **GIVEN** 用户的 workflow YAML 在 `workflow.runs[*].init_vars` 中使用 YAML merge key 复用变量映射
- **WHEN** 编辑器使用生成的 `workflow.gen.json` 做 schema-only 校验
- **THEN** MUST NOT 报告 `propertyNames` pattern mismatch for key `<<`

