# yaml-dsl-runtime-policy-boundary Specification

## Purpose
将 runtime policy 从 YAML 主线迁出到 Python/CLI runtime entrypoints，并建立清晰的 policy boundary：parser-only 路径不运行 runtime-only diagnostics，runtime-only diagnostics 仅在具备 effective runtime policy 的边界运行。

## Related Concepts
- runtime policy boundary
- runtime entrypoints (Python/CLI)
- parser-only vs policy-aware 边界
- workflow preflight
- runtime-only diagnostics
- derived runtime policy
## Requirements
### Requirement: demand runtime-policy fields MUST move out of YAML mainline

demand 侧明显属于 runtime policy 的字段 MUST 从 YAML 主线迁出到 Python / CLI runtime entrypoints:

- `guardrails.*` MUST 迁出 YAML
- `retry.*` MUST 迁出 YAML
- `batch_size` MUST 迁出 YAML(作为 runtime policy 不允许在 YAML 主线 authoring)
- demand `failure_policy` MUST 迁出 YAML
- `include_full_error_message` MUST 迁出 YAML
- `validate_unique_field_names` MUST 迁出 YAML

**Note:** 本要求约束的是 “runtime policy 的主线 authoring surface”。系统 MUST NOT 把 `batch_size` 等 runtime policy 重新引入 YAML authoring；若需要在运行时推导 derived 值,应通过 runtime entrypoints 的 typed surface（例如 hooks）实现,并保持调用方显式控制优先级最高。

#### Scenario: demand runtime-policy fields in YAML are rejected with migration guidance
- **GIVEN** 某个 demand YAML 仍声明 `include_full_error_message` 或 `validate_unique_field_names` 或顶层 `batch_size`
- **WHEN** 用户执行 validate 或运行入口解析
- **THEN** 系统 MUST 拒绝其作为主线 authoring 字段
- **AND** MUST 给出迁移到 runtime entrypoint 的提示

#### Scenario: runtime policy declarations remain rejected in YAML
- **GIVEN** 某个 demand YAML 试图声明顶层 `batch_size` 或其它 runtime policy 字段
- **WHEN** 用户执行 validate 或运行入口解析
- **THEN** 系统 MUST 拒绝其作为主线 authoring 字段
- **AND** MUST 给出迁移到 runtime entrypoint 的提示

### Requirement: environment-sensitive workflow runtime knobs MUST move out of YAML

workflow 中明显与环境、性能预算或发布策略绑定的 runtime knobs MUST 从 YAML 迁出（runtime policy boundary）：

- `workflow.options` MUST NOT 再作为 workflow YAML 的 authoring surface（出现时 MUST fail-fast，并给出迁移指引）。
- 以下旧字段（含子字段）MUST 被视为 runtime policy 并从 YAML 迁出：
  - `workflow.options.max_concurrency`
  - `workflow.options.failure_policy`
  - `workflow.options.scheduler`
  - `workflow.options.cache_pool`
  - `workflow.options.resources_wait`
  - `workflow.options.output_staging`
- `workflow.options.ctx` 作为“ctx size guardrails”配置入口 MUST 被移除；框架不再对 ctx payload 做 size-limit 报错（见 `yaml-dsl-workflow` 规范的 ctx 部分）。

#### Scenario: workflow runtime policy in YAML is rejected with migration guidance
- **GIVEN** workflow YAML 声明 `workflow.options`（例如 `workflow.options.max_concurrency`）
- **WHEN** 用户执行 workflow validate 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

#### Scenario: workflow staging/wait policy is configured through runtime entrypoints
- **WHEN** 用户需要调整共享资源等待超时或 staging 保留策略
- **THEN** 系统 MUST 通过 Python / CLI runtime entrypoints（`workflow_runtime_options.resources_wait` / `workflow_runtime_options.output_staging`）表达这些策略
- **AND** MUST NOT 继续依赖 workflow YAML 中的对应字段

### Requirement: workflow `failure_policy` MUST remain a stable orchestration knob

workflow `failure_policy` MUST 保持为稳定的 orchestration 语义并与 demand `failure_policy` 分离演进，但其配置 MUST 位于 runtime policy boundary（而不是 YAML authoring surface）：

- workflow `failure_policy` MUST 继续参与 workflow 语义校验（在 effective runtime policy 边界）
- 它 MUST 与 demand `failure_policy` 分离演进
- workflow YAML MUST NOT 再接受 `workflow.options.failure_policy` 作为 authoring 字段

#### Scenario: workflow failure policy is configured through runtime entrypoints
- **GIVEN** 调用方在运行入口提供 `workflow_runtime_options.execution.failure_policy=primary_only`
- **WHEN** 用户执行 `run_workflow(...)`
- **THEN** workflow MUST 继续执行后续 nodes（符合 `primary_only` 语义）

### Requirement: extracted runtime policy MUST be controllable by runtime entrypoints and environment selection
迁出后的 runtime policy MUST 由运行入口显式控制:

- Python / CLI runtime entrypoints MUST 提供 typed surface
- 对性能损耗显著的 guardrails,系统 MUST 支持按环境启停
- workflow compile 期间若为结构预加载 demand YAML，系统 MUST NOT 在尚未拿到 effective runtime policy 前抢跑 runtime-only diagnostics

#### Scenario: expensive guardrails are enabled only in selected environments
- **WHEN** 某个 guardrail 在开发环境需要开启而生产环境需要关闭
- **THEN** 用户 MUST 能通过 runtime entrypoint 或环境选择切换该行为
- **AND** 不需要修改 YAML authoring 文件

#### Scenario: workflow compile does not preempt demand diagnostics policy
- **GIVEN** 某个 workflow run 引用的 demand YAML 含有 intentional duplicate effective field display names
- **WHEN** 系统执行 workflow compile 阶段的结构预加载
- **THEN** 系统 MUST NOT 因 `validate_unique_field_names` 在该阶段直接失败
- **AND** duplicate-name 诊断 MUST 等到具备 effective runtime policy 的边界再决定是否报错（例如 workflow preflight 或 demand runtime compile）

### Requirement: workflow MUST run inferable runtime-only diagnostics at the effective-policy boundary (preflight)
当 workflow 具备 per-run effective runtime policy（包括 run patches）以及 effective outputs/resources 口径后,系统 MUST 在进入 engine 调度前运行一组 inferable diagnostics（workflow preflight）。

该机制 MUST 满足:
- diagnostics MUST NOT 在 workflow compile/preload 阶段抢跑
- diagnostics MUST 基于 effective policy/overrides 口径（避免 YAML 与 override 口径不一致导致误报/漏报）

#### Scenario: preload stays structural but preflight may reject duplicates
- **GIVEN** 某个 workflow run 引用的 demand YAML 含有 duplicate effective field display names
- **WHEN** 系统执行 workflow compile/preload 阶段的结构预加载（例如 `compile_workflow_ir(...)`）
- **THEN** 系统 MUST NOT 因该诊断直接失败
- **AND** 在具备 effective runtime policy 的 workflow preflight 边界上,系统 MAY 进一步决定是否报错

### Requirement: demand parsing MUST be parser-only; runtime-only diagnostics MUST run only at policy-aware boundaries
系统 MUST 将 demand 的“解析/结构化”与“runtime-only diagnostics/compile”彻底分离：

- demand YAML 的 parse/loader API MUST 为 parser-only（只负责解析与结构抽取）
- parser-only 路径 MUST NOT 运行任何依赖 effective runtime policy 的 diagnostics（例如 `validate_unique_field_names`）
- runtime-only diagnostics MUST 仅在具备 effective runtime policy 的边界运行（例如 workflow preflight 或 demand runtime compile）

#### Scenario: parser-only demand load does not fail on duplicate display names
- **GIVEN** 某个 demand fields 存在 duplicate effective field display names
- **WHEN** 系统仅执行 parser-only 的解析/结构预加载
- **THEN** 解析/预加载 MUST 成功返回结构信息
- **AND** MUST NOT 因 `validate_unique_field_names` 直接失败

### Requirement: parser-only demand loader MUST NOT expose runtime-only diagnostics knobs
为减少误用面并从结构上约束边界，系统提供的 parser-only demand loader MUST NOT 暴露任何“启用/禁用 runtime-only diagnostics”的参数（例如 `validate_unique_field_names` 这类开关）；runtime-only diagnostics 必须只能通过 policy-aware 边界的 typed runtime policy 输入控制。

#### Scenario: parser-only loader cannot be called with validate_unique_field_names
- **WHEN** 调用方尝试以 `validate_unique_field_names=...` 调用 parser-only demand loader
- **THEN** 该调用 MUST 不可用（例如参数不存在或直接报错）

### Requirement: derived runtime policy MUST NOT reduce caller control

当系统通过 runtime hooks 推导 derived runtime policy（例如 derived `batch_size`）时,系统 MUST 保持调用方的显式 runtime policy 具有最高优先级:

- 调用方显式提供 `RunOptions(batch_size=<int|None>)` 时,系统 MUST 使用显式值且 MUST 跳过 `pre_use_batch_size` policy signal。
- workflow per-run patch 显式提供 `batch_size=<int|None>` 时,系统 MUST 使用 patch 值且 MUST 跳过 `pre_use_batch_size` policy signal。

#### Scenario: explicit batch_size wins over policy signal
- **WHEN** 调用方显式传入 `RunOptions(batch_size=8000)`
- **THEN** effective `batch_size` MUST 为 `8000`
- **AND** 系统 MUST NOT 发射 `pre_use_batch_size` policy signal
