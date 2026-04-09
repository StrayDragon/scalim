# yaml-dsl-lsp-server Specification (Delta)

## ADDED Requirements

### Requirement: LSP server MUST provide field intelligence for aggregate output field references
系统 MUST 在 `outputs[*].aggregate` 相关结构中，为所有 field-id 引用点提供 completion/hover/definition，并满足：

- completion MUST 支持 Ctrl+Space 手动触发（包含空 scalar 与空 list item 场景）
- definition MUST 能跳转到字段声明位置（跨 imports 展开仍可定位）
- hover SHOULD 展示字段摘要（与现有字段卡片一致），不可解析时 MUST 返回空但不得崩溃

覆盖范围至少包括：

- `outputs[*].aggregate.group_by[*]`
- `outputs[*].aggregate.fields.*.*.field`
- `outputs[*].aggregate.fields.*.*.fields[*]`
- `outputs[*].aggregate.fields.*.rank.*.by`

#### Scenario: completion works for empty aggregate group_by list item
- **GIVEN** 某 demand YAML 存在 `outputs[*].aggregate.group_by` 且光标位于空 list item（例如 `- <cursor>`）
- **WHEN** 用户在该位置触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表

#### Scenario: definition resolves a field_id referenced by an aggregate metric
- **GIVEN** 某 demand YAML 中存在 `aggregate.fields.*.*.field: some_field_id`
- **WHEN** 用户对 `some_field_id` 触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `fields.some_field_id` 的声明位置（或 imports 展开后的真实声明位置）
