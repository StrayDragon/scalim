## ADDED Requirements

### Requirement: schema 为 `value_cast` 增加 `decimal` 枚举值
系统 MUST 在生成的 YAML DSL JSON Schema 中为源字段 `value_cast` 提供枚举值 `decimal`,并在 hover 文案中说明其语义为“转换为 `Decimal`”.

#### Scenario: schema 生成结果包含 decimal
- **WHEN** 运行 schema 生成脚本
- **THEN** `demand.gen.json` 中 `value_cast` 的 enum MUST 包含 `decimal`

