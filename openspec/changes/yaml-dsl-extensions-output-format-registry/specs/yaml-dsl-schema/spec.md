## ADDED Requirements

### Requirement: canonical schema 允许 outputs 使用自定义 `container.type` 与 `container.options`
系统 SHALL 在 canonical schema 中允许 `outputs[*].container` 使用扩展的输出格式形态:

- `outputs[*].container.type`: string format id(不再限于固定枚举)
- `outputs[*].container.options`: object(自由 dict),用于透传扩展配置

#### Scenario: schema-only 校验接受 custom container.type + options
- **GIVEN** 一份 YAML outputs 使用 `container.type: parquet`
- **AND** 同时声明 `container.options: {compression: zstd}`
- **WHEN** 使用 canonical schema 进行 schema-only 校验
- **THEN** 校验 MUST 通过
