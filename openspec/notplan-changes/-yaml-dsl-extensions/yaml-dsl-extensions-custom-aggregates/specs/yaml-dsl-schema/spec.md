## ADDED Requirements

### Requirement: canonical schema 允许 outputs.aggregate 使用 kind/ref 形态
系统 SHALL 在 canonical schema 中允许 `outputs[*].aggregate` 同时表达:

- 内置 `group_by`(保持现状)
- 自定义 kind: `aggregate.kind` + `aggregate.options`
- 自定义 ref: `aggregate.ref` + `aggregate.config`

其中:
- `options/config` MUST 为 object(自由 dict),用于透传扩展配置

#### Scenario: schema-only 校验接受 aggregate.kind + options
- **GIVEN** 一份 YAML outputs 使用 `aggregate.kind: pivot`
- **AND** 同时声明 `aggregate.options: {group_by: [province], metric: amount}`
- **WHEN** 使用 canonical schema 进行 schema-only 校验
- **THEN** 校验 MUST 通过
