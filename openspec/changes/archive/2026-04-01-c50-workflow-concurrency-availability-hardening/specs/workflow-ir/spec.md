## ADDED Requirements

### Requirement: WorkflowOptionsIr MUST carry resources_wait from YAML to runtime
系统 MUST 扩展 workflow 编译产物中的 options(IR),确保 runtime 能消费 workflow-level 的资源等待与诊断策略:

- Workflow IR 的 `options` MUST 包含结构化字段 `resources_wait`
- `resources_wait` MUST 至少包含:
  - `max_wait_s`
  - `diagnostics.enabled`
  - `diagnostics.warn_after_s`
  - `diagnostics.repeat_every_s`(可选)
  - `diagnostics.capture_owner_callsite`(可选)
- runtime 构造共享资源管理器时 MUST 仅依赖 IR options(不得再从资源定义隐式推断策略)

#### Scenario: options are present in compiled IR
- **GIVEN** workflow YAML 配置了 `workflow.options.resources_wait`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR 的 `options` MUST 包含对应字段且值与 YAML 等价
