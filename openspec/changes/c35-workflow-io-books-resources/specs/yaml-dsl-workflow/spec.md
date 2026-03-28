## ADDED Requirements

### Requirement: workflow YAML MUST use `workflow.resources.books` and MUST reject `writes` authoring surface
系统 MUST 将 workflow YAML 的共享输出资源入口收敛为 `workflow.resources.books`,并将 `workflow.runs[*].writes` 视为已移除字段:

- `workflow.resources.books` MAY 存在且 MUST 为 mapping
- `workflow.runs[*].writes` 出现时 MUST fail-fast 并给出迁移提示(迁移到 demand outputs 的 `to/write`)

#### Scenario: workflow YAML rejects removed writes field
- **GIVEN** workflow YAML 某个 run 包含 `writes: [...]`
- **WHEN** workflow 被解析/校验/编译
- **THEN** 系统 MUST fail-fast 并指出 `workflow.runs[*].writes`

