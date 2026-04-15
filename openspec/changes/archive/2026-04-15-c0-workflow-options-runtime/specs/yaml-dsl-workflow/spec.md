# yaml-dsl-workflow (delta) Specification

## MODIFIED Requirements

### Requirement: Workflow YAML declares runs and options
系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。
workflow MUST 包含:
- `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径,并支持可选的 `depends_on` 与 `init_vars`
- `workflow.resources`: 可选的共享资源定义（例如 books 等）
- `workflow.options` MUST NOT 出现在 YAML authoring surface（runtime policy boundary; 详见 `yaml-dsl-runtime-policy-boundary`）。

#### Scenario: workflow file passes schema validation
- **WHEN** workflow YAML 包含 `workflow.runs`（可选包含 `workflow.resources`）
- **AND** workflow YAML 不包含 `workflow.options`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: resources_wait in workflow.options is rejected
- **GIVEN** workflow YAML 声明 `workflow.options.resources_wait`
- **WHEN** 用户执行 workflow validate 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示该字段已迁出 YAML 并指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

### Requirement: workflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)
系统 MUST 在一次 workflow 执行中维护一个 workflow-level ctx store,用于在依赖边上传递小体量上下文:
- ctx MUST 以 `workflow_node_id` 为命名空间(对 demand 节点等于 workflow YAML 的 `runs[*].id`)
- ctx 值 MUST 为 JSON-like 对象(标量/小 list/dict)
- 框架 MUST NOT 对 ctx payload 施加 size-limit 护栏（不得因 payload 大小 fail-fast；payload 治理由调用方负责）
- 系统 MUST 禁止将 rows/dataset/大型输出放入 ctx；大对象必须通过 artifacts/resources 路径表达
- ctx store MUST 线程安全(并发执行下可安全读写)

#### Scenario: ctx is only readable from dependency closure
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 尝试读取 `{$ctx: {node: A, key: output_path}}`
- **THEN** 系统 MUST fail-fast 并报告“ctx 引用超出 deps 可见范围”

### Requirement: workflow.options.resources_wait MUST configure join/wait diagnostics and timeout
系统 MUST 提供 workflow-level 的 resources wait 配置,作为 inflight join/wait 的 SSOT；该配置属于 runtime policy boundary：

- workflow YAML MUST NOT 再接受 `workflow.options.resources_wait`（出现时 MUST fail-fast，并指向 runtime entrypoints）
- runtime entrypoints MUST 允许通过 `workflow_runtime_options.resources_wait`（或等价 typed surface）配置以下字段：
  - `max_wait_s` MUST 为有限正数值(秒),缺省时 MUST 等价于 600
  - `diagnostics` MAY 缺省;若提供,MUST 为 mapping
    - `diagnostics.enabled` MUST 为 bool(缺省等价于 false)
    - `diagnostics.warn_after_s` MUST 为有限非负数值(秒)(缺省等价于 30)
    - `diagnostics.repeat_every_s` MAY 缺省;若提供,MUST 为有限正数(秒)
    - `diagnostics.capture_owner_callsite` MAY 缺省;若提供,MUST 为 bool

#### Scenario: resources_wait in YAML is rejected with an actionable migration hint
- **WHEN** workflow YAML 声明 `workflow.options.resources_wait`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

### Requirement: workflow.options.output_staging MUST configure staging directory and cleanup policy
系统 MUST 提供 workflow-level 的 output staging 配置,作为共享输出 staging/publish 行为的 SSOT；该配置属于 runtime policy boundary：

- workflow YAML MUST NOT 再接受 `workflow.options.output_staging`（出现时 MUST fail-fast，并指向 runtime entrypoints）
- runtime entrypoints MUST 允许通过 `workflow_runtime_options.output_staging`（或等价 typed surface）配置以下字段：
  - `dir_name` MUST 为非空字符串且不包含路径分隔符(`/`或`\`);缺省时 MUST 等价于 `.scalim-staging`
  - `keep_on_success` MUST 为 bool;缺省时 MUST 等价于 `false`
  - `keep_on_failure` MUST 为 bool;缺省时 MUST 等价于 `true`

#### Scenario: output_staging in YAML is rejected with an actionable migration hint
- **WHEN** workflow YAML 声明 `workflow.options.output_staging`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

### Requirement: workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
系统 MUST 提供 workflow-scope cache pool 能力以支持跨 nodes 复用（例如 `preload_forever`）；但 cache pool 的配置入口 MUST 位于 runtime policy boundary 并保持对外接口受限：

- workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`（出现时 MUST fail-fast，并指向 runtime entrypoints）
- cache_pool 的可用配置 MUST 以封闭集合的 preset 方式提供（避免自由组合 knobs 导致维护成本上升）
- 旧字段 `workflow.options.share_preload_cache` MUST 继续被拒绝，并给出迁移到 runtime preset 的提示

#### Scenario: cache_pool in YAML is rejected with migration guidance
- **WHEN** workflow YAML 包含 `workflow.options.cache_pool`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指向 runtime entrypoints（例如 `run_workflow(..., workflow_runtime_options=...)`）

#### Scenario: share_preload_cache is rejected
- **WHEN** workflow YAML 包含 `workflow.options.share_preload_cache`
- **THEN** 系统 MUST fail-fast 报错（提示迁移到 runtime cache_pool preset）

NOTE: cache pool 的语义(冲突策略/生命周期/预算/可观测性)由 `workflow-cache-pool` 能力规范定义.

## REMOVED Requirements

### Requirement: ctx guardrails MUST be configurable via `workflow.options.ctx`

**Reason**：ctx payload 的规模治理属于业务侧/环境侧 control-plane；框架内置 size-limit 只能在触发时失败报错，无法提供真正的治理手段，且引入高维护成本与大量“环境差异配置”的 SSOT 破坏。

**Migration**：
- 删除 workflow YAML 中的 `workflow.options.ctx`（同时删除整个 `workflow.options`）。
- 业务侧自行约束 ctx payload：仅发布 ids/paths/summary 等小对象；大型对象通过 artifacts/resources 传递。
- 若需要“超限即失败”的行为，应在业务侧 hooks/observers 中实现，并与业务日志/告警系统集成。

#### Scenario: ctx guardrails config is rejected with an actionable migration hint
- **GIVEN** workflow YAML 仍包含 `workflow.options.ctx`
- **WHEN** 用户执行 workflow validate 或运行入口解析
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示 ctx guardrails 已移除且 workflow.options 已迁出 YAML（指向 runtime entrypoints）
