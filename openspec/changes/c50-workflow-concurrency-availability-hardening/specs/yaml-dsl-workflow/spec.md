## ADDED Requirements

### Requirement: workflow.options.resources_wait MUST configure join/wait diagnostics and timeout
系统 MUST 扩展 workflow YAML 的 `workflow.options` 支持结构化的 `resources_wait` 配置,作为 inflight join/wait 的 SSOT:

- `workflow.options.resources_wait.max_wait_s` MUST 为有限非负数值(秒),缺省时 MUST 等价于 600
- `workflow.options.resources_wait.warn_after_s` MUST 为有限非负数值(秒),缺省时 MUST 等价于 30
- `workflow.options.resources_wait.repeat_every_s` MAY 缺省;若提供,MUST 为有限正数(秒)
- `workflow.options.resources_wait.capture_owner_callsite` MAY 缺省;若提供,MUST 为 bool
- 该配置 MUST 纳入 schema-only 校验并在解析失败时 fail-fast

#### Scenario: resources_wait passes schema validation
- **WHEN** workflow YAML 声明 `workflow.options.resources_wait` 且字段类型合法
- **THEN** schema-only 校验 MUST 通过

### Requirement: workflow.options.write_locks MUST configure write lock backend and governance
系统 MUST 扩展 workflow YAML 的 `workflow.options` 支持结构化的 `write_locks` 配置,作为 workflow 写锁策略的 SSOT:

- `workflow.options.write_locks.backend` MUST 为枚举: `file|mkdir|none`
- `workflow.options.write_locks.stale_after_s` MAY 缺省;若提供,MUST 为有限非负数值(秒)
- `workflow.options.write_locks.force` MAY 缺省;若提供,MUST 为 bool
- 该配置 MUST 纳入 schema-only 校验并在解析失败时 fail-fast

#### Scenario: write_locks passes schema validation
- **WHEN** workflow YAML 声明 `workflow.options.write_locks.backend=mkdir`
- **THEN** schema-only 校验 MUST 通过

## MODIFIED Requirements

### Requirement: Workflow YAML declares runs and options
系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。
workflow MUST 包含:
- `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径,并支持可选的 `depends_on` 与 `init_vars`
- `workflow.options`: 运行选项,包含 `max_concurrency`、`failure_policy`、`cache_pool`(可选)、`ctx`(可选)、`resources_wait`(可选) 与 `write_locks`(可选)

#### Scenario: workflow file passes schema validation
- **WHEN** workflow YAML 同时包含 `workflow.runs` 与 `workflow.options`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: resources_wait and write_locks are allowed in workflow.options
- **GIVEN** workflow YAML 声明 `workflow.options.resources_wait` 与 `workflow.options.write_locks`
- **WHEN** 运行 schema-only 校验
- **THEN** 校验 MUST 通过
