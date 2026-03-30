## ADDED Requirements

### Requirement: Workflow IR options MUST carry resource wait and write-lock policies

系统 MUST 将 workflow 的“资源等待上限”与“写锁后端/治理”作为 IR 编译边界的一部分,并通过 `WorkflowOptionsIr` 传递给 runtime.

约束:

- `WorkflowOptionsIr` MUST 包含资源等待策略（至少 `max_wait_s` 与 wait diagnostics 配置）
- `WorkflowOptionsIr` MUST 包含写锁策略（至少 `backend` 与可选的 stale/force 配置）
- 当 workflow YAML 未显式配置这些选项时,IR MUST 仍携带明确默认值（避免 runtime 侧隐式猜测）

#### Scenario: compiling a workflow produces options with explicit defaults
- **GIVEN** workflow YAML 未声明 `workflow.options.resources_wait` 与 `workflow.options.write_locks`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** `WorkflowOptionsIr` MUST 包含 `max_wait_s=600` 与 `backend=file` 的显式默认值

