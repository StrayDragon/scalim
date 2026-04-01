## ADDED Requirements

### Requirement: workflow.options.output_staging MUST configure staging directory and cleanup policy
系统 MUST 扩展 workflow YAML 的 `workflow.options` 支持结构化的 `output_staging` 配置,作为共享输出 staging/publish 行为的 SSOT:

- `workflow.options.output_staging.dir_name` MUST 为非空字符串且不包含路径分隔符(`/`或`\`);缺省时 MUST 等价于 `.scalim-staging`
- `workflow.options.output_staging.keep_on_success` MUST 为 bool;缺省时 MUST 等价于 `false`
- `workflow.options.output_staging.keep_on_failure` MUST 为 bool;缺省时 MUST 等价于 `true`
- 该配置 MUST 纳入 schema-only 校验并在解析失败时 fail-fast

#### Scenario: output_staging passes schema validation
- **WHEN** workflow YAML 声明 `workflow.options.output_staging` 且字段类型合法
- **THEN** schema-only 校验 MUST 通过

