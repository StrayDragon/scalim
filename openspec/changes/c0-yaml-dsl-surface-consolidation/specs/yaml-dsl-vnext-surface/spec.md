# yaml-dsl-vnext-surface Specification

**状态: 🚧 提案**

## Purpose

定义 YAML DSL vNext 的 authoring 核心面、组织原则与分层边界，目标是显著降低维护成本并阻止配置面继续扩张：
- YAML 主要承载 declarative 的业务建模
- runtime control plane（策略/诊断/治理）优先下沉到 Python/CLI/profile

## ADDED Requirements

### Requirement: vNext demand YAML MUST reject runtime control-plane keys

vNext demand YAML 的 authoring 面 MUST 仅包含业务建模与少量可移植 IO 声明。

vNext demand YAML MUST 拒绝以下“运行时控制面”类 keys（出现即 fail-fast，并给出迁移提示）：
- `observability`
- `guardrails`
- `retry`（含 `main_source.retry` / `sources.*.retry`）
- `batch_size`
- `include_full_error_message`
- `validate_unique_field_names`
- `meta` / `audit`
- `failure_policy`

#### Scenario: demand vNext rejects observability
- **WHEN** vNext demand YAML 包含顶层 `observability`
- **THEN** 校验 MUST 失败
- **AND** 错误信息 MUST 提示改用 `scalim.dsl.by_yaml.run(..., components=.../overrides=...)` 或 CLI flags 控制观测/诊断

#### Scenario: demand vNext rejects retry
- **WHEN** vNext demand YAML 包含 `retry` 或 `sources.*.retry`
- **THEN** 校验 MUST 失败
- **AND** 错误信息 MUST 提示改用 `RunOptions.loader_retry`（或 profile/preset）提供重试策略

### Requirement: vNext workflow YAML MUST keep declarative orchestration surface small

vNext workflow YAML MUST 保持“编排声明”优先，避免成为 runtime 控制面。

vNext workflow YAML 的 `workflow.options` MUST 仅允许以下稳定入口：
- `max_concurrency`
- `failure_policy`
- `cache_pool`（若启用）
- `ctx`（护栏）

其它 diagnostics/staging/wait 类入口（例如 `resources_wait.diagnostics`、`output_staging`）在 vNext 中 MUST 被拒绝，并迁移到 Python `run_workflow(...)` 参数或 CLI flags。

#### Scenario: workflow vNext rejects diagnostics options
- **WHEN** vNext workflow YAML 包含 `workflow.options.resources_wait.diagnostics`
- **THEN** 校验 MUST 失败
- **AND** 错误信息 MUST 指向迁移路径（Python 入口参数或 CLI flags）

### Requirement: vNext YAML organization MUST be KV-first

vNext YAML DSL MUST 采用 KV-first 组织原则：
- 任何需要稳定 ID/引用/复用的结构 MUST 使用 mapping，且 mapping key 即为该对象的 stable id（例如 `sources.<source_id>`、`resources.books.<book_id>`）。
- 仅当顺序语义不可替代时允许使用 list（例如 `workflow.runs`、`relation.steps`、`outputs`）。

#### Scenario: outputs items require stable name
- **WHEN** vNext demand YAML 声明了 `outputs` list
- **AND** 任一 `outputs[*]` 缺失 `name` 或 `name` 为空
- **THEN** 校验 MUST 失败并指向 `outputs[*].name`
