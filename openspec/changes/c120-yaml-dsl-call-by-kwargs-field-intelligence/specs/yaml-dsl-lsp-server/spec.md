# yaml-dsl-lsp-server Specification (Delta)

## ADDED Requirements

### Requirement: LSP server MUST provide field intelligence for field-id tokens inside `call_by` kwargs values
系统 MUST 在 `call_by` 字符串参数段内，为 kwargs 的 `=` **右侧** field-id token 提供 field 智能（completion/hover/definition），并满足：

- definition MUST 跳转到字段声明（含跨 imports 展开的真实声明位置）
- hover SHOULD 展示字段摘要（与 compute/where 的字段卡片一致），不可解析时 MUST 返回空但不得崩溃
- completion MUST 支持 Ctrl+Space 手动触发，并能在 `x=` 的空值场景返回候选列表
- `=` 左侧 kwargs 名称 MUST NOT 被当作 field-id（hover/definition 返回空）

#### Scenario: go-to-definition resolves a kwargs value field_id
- **GIVEN** YAML 声明 `fields.order_amount: ...`
- **AND** 存在 `call_by: "pkg.mod:fn(order_amount=order_amount)"`
- **WHEN** 用户对 `order_amount=order_amount` 的右侧 `order_amount` 触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `fields.order_amount` 的声明位置

#### Scenario: completion works for empty kwargs value
- **GIVEN** 存在 `call_by: "pkg.mod:fn(order_amount=)"`
- **WHEN** 用户在 `=` 右侧触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表
