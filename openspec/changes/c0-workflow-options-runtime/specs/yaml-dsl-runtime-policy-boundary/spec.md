# yaml-dsl-runtime-policy-boundary (delta) Specification

## MODIFIED Requirements

### Requirement: environment-sensitive workflow runtime knobs MUST move out of YAML

workflow 中明显与环境、性能预算或发布策略绑定的 runtime knobs MUST 从 YAML 迁出（runtime policy boundary）：

- `workflow.options` MUST NOT 再作为 workflow YAML 的 authoring surface（出现时 MUST fail-fast，并给出迁移指引）。
- 以下旧字段（含子字段）MUST 被视为 runtime policy 并从 YAML 迁出：
  - `workflow.options.max_concurrency`
  - `workflow.options.failure_policy`
  - `workflow.options.cache_pool`
  - `workflow.options.resources_wait`
  - `workflow.options.output_staging`
- `workflow.options.ctx` 作为“ctx size guardrails”配置入口 MUST 被移除；框架不再对 ctx payload 做 size-limit 报错（见 `yaml-dsl-workflow` 规范的 ctx 部分）。

#### Scenario: workflow runtime policy in YAML is rejected with migration guidance
- **GIVEN** workflow YAML 声明 `workflow.options`（例如 `workflow.options.max_concurrency`）
- **WHEN** 用户执行 workflow validate 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime=...)`）

#### Scenario: workflow staging/wait policy is configured through runtime entrypoints
- **WHEN** 用户需要调整共享资源等待超时或 staging 保留策略
- **THEN** 系统 MUST 通过 Python / CLI runtime entrypoints（`workflow_runtime.resources_wait` / `workflow_runtime.output_staging`）表达这些策略
- **AND** MUST NOT 继续依赖 workflow YAML 中的对应字段

### Requirement: workflow `failure_policy` MUST remain a stable orchestration knob

workflow `failure_policy` MUST 保持为稳定的 orchestration 语义并与 demand `failure_policy` 分离演进，但其配置 MUST 位于 runtime policy boundary（而不是 YAML authoring surface）：

- workflow `failure_policy` MUST 继续参与 workflow 语义校验（在 effective runtime policy 边界）
- 它 MUST 与 demand `failure_policy` 分离演进
- workflow YAML MUST NOT 再接受 `workflow.options.failure_policy` 作为 authoring 字段

#### Scenario: workflow failure policy is configured through runtime entrypoints
- **GIVEN** 调用方在运行入口提供 `workflow_runtime.execution.failure_policy=primary_only`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** workflow MUST 继续执行后续 nodes（符合 `primary_only` 语义）
