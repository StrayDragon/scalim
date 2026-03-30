## MODIFIED Requirements

### Requirement: Workflow YAML declares runs and options
系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。
workflow MUST 包含:
- `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径,并支持可选的 `depends_on` 与 `init_vars`
- `workflow.options`: 运行选项,包含：
  - `max_concurrency`
  - `failure_policy`
  - `cache_pool`（可选）
  - `ctx`（可选）
  - `resources_wait`（可选,默认 `max_wait_s=600`）
  - `write_locks`（可选,默认 `backend=file`）

`workflow.options.resources_wait` 用于控制 workflow 共享资源的 joinable wait 上限与等待诊断阈值；
`workflow.options.write_locks` 用于统一控制共享输出写锁后端与 stale 治理策略.

#### Scenario: workflow file passes schema validation
- **WHEN** workflow YAML 同时包含 `workflow.runs` 与 `workflow.options`
- **THEN** schema-only 校验 MUST 通过
- **AND** 当 `workflow.options.resources_wait` 与 `workflow.options.write_locks` 出现时,校验仍 MUST 通过

