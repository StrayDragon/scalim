# yaml-dsl-lsp-server Specification (Delta)

## ADDED Requirements

### Requirement: LSP server MUST provide field intelligence for aggregate output field references
系统 MUST 在 `outputs[*].aggregate` 相关结构中，为所有 field-id 引用点提供 completion/hover/definition，并满足：

- completion MUST 支持 Ctrl+Space 手动触发（包含空 scalar 与空 list item 场景）
- definition MUST 能跳转到字段声明位置（跨 imports 展开仍可定位）
- hover SHOULD 展示字段摘要（与现有字段卡片一致），不可解析时 MUST 返回空但不得崩溃

覆盖范围至少包括：

- `outputs[*].aggregate.group_by[*]`
- `outputs[*].aggregate.group_by[*][*]`（复合 key 内层 token）
- `outputs[*].aggregate.fields.*.*.field`
- `outputs[*].aggregate.fields.*.*.fields[*]`
- `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).by`
- `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).partition_by[*]`
- `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).order_by[*]`
- `outputs[*].aggregate.fields.*.score_by_rank.rank_field`

completion MUST 返回分层候选并稳定排序（按优先级从高到低）：
1) `outputs[*].aggregate.fields` 的 out_field_id（mapping key）
2) `outputs[*].aggregate.group_by` 的 field_id
3) 全局可见 field_id（低优先 fallback；MUST 以 detail/label 明确标注来源，避免误导）

definition MUST 支持多 locations，并满足稳定排序：
- 若 token 命中 out_field_id，则该 out_field 的定义点 MUST 为第一个候选
- 其余候选（如全局 field_id 定义）MUST 作为后续候选稳定排序+去重

#### Scenario: completion works for empty aggregate group_by list item
- **GIVEN** 某 demand YAML 存在 `outputs[*].aggregate.group_by` 且光标位于空 list item（例如 `- <cursor>`）
- **WHEN** 用户在该位置触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表

#### Scenario: definition resolves a field_id referenced by an aggregate metric
- **GIVEN** 某 demand YAML 中存在 `aggregate.fields.*.*.field: some_field_id`
- **WHEN** 用户对 `some_field_id` 触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `fields.some_field_id` 的声明位置（或 imports 展开后的真实声明位置）

#### Scenario: rank.by resolves aggregate out_field_id first, then global field fallback
- **GIVEN** 某 demand YAML 中存在 `outputs[0].aggregate.fields.sum_amount: {sum: {field: order_amount}}`
- **AND** 存在 `outputs[0].aggregate.fields.rank: {dense_rank: {by: sum_amount, order: desc}}`
- **WHEN** 用户对 `by: sum_amount` 的 `sum_amount` 触发 go-to-definition
- **THEN** 系统 MUST 首选跳转到 `outputs[0].aggregate.fields.sum_amount` 的 key 位置
- **AND** 系统 MAY 返回额外候选（例如同名全局 field 定义），但必须排在后面且稳定排序
