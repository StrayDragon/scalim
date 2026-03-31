## ADDED Requirements

### Requirement: demand JSON Schema MUST validate source identifiers and reject empty loader/key
系统 MUST 在生成的 demand JSON Schema(`demand.gen.json`)中表达并拒绝以下形态,以与 runtime 语义保持一致:

- `main_source.source_id` MUST 匹配 `^[a-zA-Z_][a-zA-Z0-9_]*$`
- `sources` mapping keys MUST 匹配同一 pattern(通过 `propertyNames`; 且为保持 `$import` 在编辑器侧可用,`propertyNames` MUST 同时允许 key 为 `$import`)
- `main_source.loader` / `sources.*.loader` MUST 为非空字符串(`minLength: 1`)
- `sources.*.key` 的 string(或 array items) MUST 为合法 `field_id`(拒绝空字符串)

#### Scenario: schema rejects invalid sources keys
- **WHEN** demand YAML 的 `sources` 出现空 key 或非法 key(例如 `\"\"`/`\"1abc\"`)
- **THEN** schema-only 校验 MUST 失败

#### Scenario: schema rejects empty loader/key
- **WHEN** `sources.orders.loader: \"\"` 或 `sources.orders.key: \"\"`
- **THEN** schema-only 校验 MUST 失败

### Requirement: demand JSON Schema MUST reject empty retry.should_retry when provided
系统 MUST 在 demand JSON Schema 中保证 `retry.should_retry` 的形态正确:

- 当用户显式提供 `retry.should_retry` 时,其 MUST 为非空字符串(`minLength: 1`)

> NOTE: schema 本体无法感知 driver injection,因此本变更不要求 schema 拒绝 `enabled=true` 且缺失 `should_retry` 的 YAML(该完整性约束由 CLI validate/schema validate 负责)。

#### Scenario: schema rejects empty should_retry string
- **WHEN** demand YAML 配置 `retry: {should_retry: \"\"}`
- **THEN** schema-only 校验 MUST 失败

### Requirement: demand JSON Schema MUST encode composed outputs invariants (streaming=true, detail fields source)
系统 MUST 在 demand JSON Schema 中表达 outputs 的关键不变量,避免 schema validate 放行但 parser 失败:

- `outputs[*].container.streaming` 若显式提供,则 MUST 为 `true`
- 当 output 未声明 `aggregate` 时(明细输出),系统 MUST 要求存在字段来源:
  - 显式提供非空 `fields`,或
  - 通过 `from` 继承字段集合
  - 为保持 `$import` 在编辑器侧可用,该约束 MUST 不阻断仅声明 `$import` 的 output_target

#### Scenario: schema rejects streaming=false
- **WHEN** `outputs[0].container.streaming=false`
- **THEN** schema-only 校验 MUST 失败

#### Scenario: schema rejects detail output without fields and without from
- **WHEN** output 未声明 `aggregate` 且同时缺失 `fields` 与 `from`
- **THEN** schema-only 校验 MUST 失败
