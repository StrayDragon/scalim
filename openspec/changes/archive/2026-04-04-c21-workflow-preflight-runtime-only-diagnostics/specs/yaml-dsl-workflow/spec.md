# yaml-dsl-workflow Specification

## ADDED Requirements

### Requirement: workflow preflight errors MUST be treated as workflow config/compile errors (independent of failure_policy)
当某个诊断被定义为 workflow preflight（engine 启动前）失败时，系统 MUST 直接 raise 并中止整个 workflow，且 MUST NOT 继续调度其它 runs（`failure_policy` 不适用）：

- 系统 MUST 直接 raise 并中止整个 workflow
- 系统 MUST NOT 将该失败视为“某个 run 的可恢复失败”并继续调度其它 runs
- `failure_policy` MUST 不影响 preflight 的失败语义

#### Scenario: primary_only does not continue on preflight failure
- **GIVEN** workflow.options.failure_policy=primary_only
- **AND** preflight 发现某个 run 存在 duplicate effective field display names 且触发 `validate_unique_field_names`
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST 直接 raise 并中止整个 workflow
- **AND** workflow MUST NOT 执行任何 run
