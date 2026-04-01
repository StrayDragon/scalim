## ADDED Requirements

### Requirement: WorkflowOptionsIr MUST carry output_staging from YAML to runtime
系统 MUST 扩展 workflow 编译产物中的 options(IR),确保 runtime 能消费 workflow-level 的 staging/publish 策略:

- Workflow IR 的 `options` MUST 包含结构化字段 `output_staging`
- `output_staging` MUST 至少包含: `dir_name`、`keep_on_success` 与 `keep_on_failure`

#### Scenario: output_staging is present in compiled IR
- **GIVEN** workflow YAML 配置了 `workflow.options.output_staging`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR 的 `options` MUST 包含对应字段且值与 YAML 等价

