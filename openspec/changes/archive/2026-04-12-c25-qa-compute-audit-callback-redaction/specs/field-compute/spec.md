# field-compute (delta) Specification

## MODIFIED Requirements

### Requirement: compute audit callback MUST support redaction
系统 MUST 提供 compute 审计能力，但 MUST 以“安全默认 + 显式 full”作为治理前提：

- 系统 MUST 提供 `redacted` 审计实现：在启用审计时仅记录表达式标识（例如 hash）与字段名列表（以及可选的结果类型/摘要），**不得**记录字段值与结果的原始内容
- 系统 MAY 提供 `full/raw` 审计实现，但该模式 MUST 为显式 opt-in（公共 API 必须能表达风险），不得以“默认/推荐”命名或隐式启用
- 系统 MUST 提供 `none`（默认）模式：默认不启用审计回调，避免在常规运行中产生额外开销与泄密风险
- 当启用 `full/raw` 模式时，系统 SHOULD 输出一次显式告警提示（例如 WARNING），提示其可能包含敏感信息且不建议在生产环境启用

#### Scenario: audit disabled does not call callback
- **GIVEN** compute 审计模式为 `none`（默认）
- **WHEN** 系统对某行数据执行 compute 表达式求值
- **THEN** 系统 MUST NOT 调用任何审计回调

#### Scenario: redacted audit logs only field names
- **GIVEN** compute 审计模式为 `redacted`
- **WHEN** 系统对某行数据执行 compute 表达式求值并触发审计
- **THEN** 审计输出 MUST 不包含字段值与结果的原始内容

#### Scenario: full audit requires explicit opt-in
- **GIVEN** 系统提供 `full/raw` 审计模式
- **WHEN** 用户未显式选择 `full/raw` 模式
- **THEN** 系统 MUST NOT 输出字段值/结果的原始内容
- **AND** 只有在显式启用 `full/raw` 模式时系统才 MAY 输出原始内容

