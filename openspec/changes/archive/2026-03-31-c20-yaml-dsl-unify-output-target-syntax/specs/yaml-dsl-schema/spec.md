## MODIFIED Requirements

### Requirement: schema MUST expose the unified output target surface and reject legacy `container`
系统 MUST 生成反映统一输出模型的 YAML DSL schema:

- MUST 暴露 `resources.files`
- MUST 暴露 `outputs[*].to.file`
- MUST 在 `outputs[*].write` 中暴露通用 header 字段
- MUST NOT 再接受 `outputs[*].container`

#### Scenario: schema exposes resources.files and to.file
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** schema MUST 暴露 `definitions.file` / `definitions.output_to.properties.file`
- **AND** 顶层 `resources` MUST 支持 `files`

#### Scenario: schema rejects legacy container surface
- **WHEN** 用户使用 `outputs[*].container`
- **THEN** schema-only 校验 MUST 失败

### Requirement: schema defaults for unified header behavior MUST be `name`
系统 MUST 将统一写入模型下的 `header_fields_output_by` 默认值设为 `name`。

约束:

- `outputs[*].write.header_fields_output_by.default` MUST 等于 `name`
- `resources.books.write_defaults` MUST NOT 暴露 `header_fields_output_by`

#### Scenario: write header_fields_output_by default is name
- **WHEN** 生成 `demand.gen.json`
- **THEN** `definitions.output_write.properties.header_fields_output_by.default` MUST 等于 `name`

### Requirement: schema exposes a switch for unique effective field display names
系统 MUST 在 schema 中暴露顶层 `validate_unique_field_names`,并明确该检查在统一 target model 下的触发条件。

hover 文案 MUST 说明:

- file: `write.include_header: true` 且 `write.header_fields_output_by: name`
- book: 该 output 会输出表头且 `write.header_fields_output_by: name`

#### Scenario: schema hover reflects unified header trigger rules
- **WHEN** 生成 `demand.gen.json`
- **THEN** `properties.validate_unique_field_names.markdownDescription` MUST 不再引用 `container`
- **AND** MUST 说明统一 `write.header_fields_output_by` 触发规则
