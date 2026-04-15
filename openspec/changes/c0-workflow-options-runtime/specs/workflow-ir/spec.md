# workflow-ir (delta) Specification

## MODIFIED Requirements

### Requirement: WorkflowOptionsIr MUST carry resources_wait from YAML to runtime
系统 MUST 扩展 workflow 编译产物中的 options(IR),确保 runtime 能消费 workflow-level 的资源等待与诊断策略。

`resources_wait` 的配置来源 MUST 位于 runtime policy boundary（而不是 workflow YAML authoring surface）：

- Workflow IR 的 `options` MUST 包含结构化字段 `resources_wait`
- `resources_wait` MUST 至少包含:
  - `max_wait_s`
  - `diagnostics.enabled`
  - `diagnostics.warn_after_s`
  - `diagnostics.repeat_every_s`(可选)
  - `diagnostics.capture_owner_callsite`(可选)
- runtime 构造共享资源管理器时 MUST 仅依赖 IR options(不得再从资源定义隐式推断策略)

#### Scenario: options are present in compiled IR
- **GIVEN** 调用方通过 runtime entrypoints 提供 `workflow_runtime.resources_wait`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR 的 `options` MUST 包含对应字段且值与该 runtime policy 等价

### Requirement: WorkflowOptionsIr MUST carry output_staging from YAML to runtime
系统 MUST 扩展 workflow 编译产物中的 options(IR),确保 runtime 能消费 workflow-level 的 staging/publish 策略。

`output_staging` 的配置来源 MUST 位于 runtime policy boundary（而不是 workflow YAML authoring surface）：

- Workflow IR 的 `options` MUST 包含结构化字段 `output_staging`
- `output_staging` MUST 至少包含: `dir_name`、`keep_on_success` 与 `keep_on_failure`

#### Scenario: output_staging is present in compiled IR
- **GIVEN** 调用方通过 runtime entrypoints 提供 `workflow_runtime.output_staging`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR 的 `options` MUST 包含对应字段且值与该 runtime policy 等价
