# yaml-dsl-lsp-server Specification (Delta)

## ADDED Requirements

### Requirement: LSP server MUST provide field intelligence for field-id tokens inside `call_by` kwargs values
系统 MUST 在 `call_by` 字符串参数段内，为 kwargs 的 `=` **右侧** field-id token 提供 field 智能（completion/hover/definition），并满足：

- definition MUST 跳转到字段声明（含跨 imports 展开的真实声明位置）
- hover SHOULD 展示字段摘要（与 compute/where 的字段卡片一致），不可解析时 MUST 返回空但不得崩溃
- completion MUST 支持 Ctrl+Space 手动触发，并能在 `x=` 的空值场景返回候选列表
- `=` 左侧 kwargs 名称 MUST NOT 被当作 field-id（hover/definition 返回空）

覆盖 callsite 至少包括：
- `fields.*.call_by`
- `outputs[*].aggregate.fields.*.call_by`
- builtin callable：`call_by: "^<id>(...)"`（head 为 builtin id）

completion MUST 返回分层候选并稳定排序（按优先级从高到低），并以 detail/label 标注候选来源：
- 在 `fields.*.call_by`：全局可见 field_id 为主集合
- 在 `outputs[*].aggregate.fields.*.call_by`：out_field_id（`aggregate.fields` key）→ group_by field_id → 全局 field_id（低优先 fallback）

definition MUST 支持多 locations：
- 若 token 在 aggregate.call_by 中命中 out_field_id，则该 out_field 的定义点 MUST 为第一个候选
- 其余候选（如全局 field_id 定义）MUST 作为后续候选稳定排序+去重

#### Scenario: go-to-definition resolves a kwargs value field_id
- **GIVEN** YAML 声明 `fields.order_amount: ...`
- **AND** 存在 `call_by: "pkg.mod:fn(order_amount=order_amount)"`
- **WHEN** 用户对 `order_amount=order_amount` 的右侧 `order_amount` 触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `fields.order_amount` 的声明位置

#### Scenario: completion works for empty kwargs value
- **GIVEN** 存在 `call_by: "pkg.mod:fn(order_amount=)"`
- **WHEN** 用户在 `=` 右侧触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表

#### Scenario: aggregate.call_by completion prefers out_field_id candidates
- **GIVEN** 存在 `outputs[0].aggregate.fields.rank: {dense_rank: {by: sum_amount}}`
- **AND** 存在 `outputs[0].aggregate.fields.score: {call_by: \"^score_by_rank(rank=rank, base=100, step=3)\"}`
- **WHEN** 用户在 `rank=` 的右侧触发 completion（Ctrl+Space）
- **THEN** completion MUST 将 `rank`（out_field_id）作为高优先候选返回
