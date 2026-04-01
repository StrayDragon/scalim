# yaml-dsl-workflow Delta Specification (c0-yaml-dsl-surface-consolidation)

## ADDED Requirements

### Requirement: workflow resources schema MUST match runtime parser allowed keys

workflow YAML 的 `workflow.resources` 属于强结构区域，schema 与 runtime parser MUST 保持一致，避免 LSP/schema validate 与 runtime 行为漂移。

在 runtime 未实现 imports expansion 的前提下：
- workflow schema MUST NOT 暴露 `workflow.resources.*.$import`
- workflow runtime 校验 MUST 对 `$import` 给出明确的 fail-fast 错误与迁移提示

#### Scenario: workflow schema rejects $import under resources
- **WHEN** 用户在 workflow YAML 中为 `workflow.resources.books.<book_id>` 提供 `$import`
- **THEN** schema-only 校验 MUST 失败

#### Scenario: runtime parser fails fast on $import under resources
- **WHEN** 用户在 workflow YAML 中为 `workflow.resources` 任意节点提供 `$import`
- **THEN** `validate_workflow_yaml_text_json` MUST 返回 ok=false
- **AND** 错误信息 MUST 提示 “workflow 暂不支持 imports/$import；请改用显式声明或由 driver 侧拼装/覆盖”

### Requirement: workflow schema/runtime drift MUST be guarded by an automated check

系统 MUST 提供 drift gate，确保 workflow schema 与 runtime parser 对关键结构（至少 `workflow.resources`）的一致性可被自动验证。

#### Scenario: CI fails when drift is introduced
- **WHEN** 维护者修改 workflow schema 或 workflow parser 导致 `workflow.resources` 允许字段集合不一致
- **THEN** drift gate MUST fail-fast 并指出不一致字段集合

