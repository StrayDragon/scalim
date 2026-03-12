## ADDED Requirements

### Requirement: Workflow YAML declares runs and options
系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。
workflow MUST 包含:
- `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径
- `workflow.options`: 运行选项,包含 `max_concurrency`、`failure_policy`、`share_preload_cache`

#### Scenario: workflow file passes schema validation
- **WHEN** workflow YAML 同时包含 `workflow.runs` 与 `workflow.options`
- **THEN** schema-only 校验 MUST 通过

### Requirement: Runs execute demand YAML via existing compilation pipeline
系统 MUST 对每个 run 的 `demand` 路径加载并编译 demand YAML,并复用现有 demand 执行链路运行得到结果。
系统 MUST 以 workflow 文件所在目录作为相对路径基准。

#### Scenario: demand path is resolved relative to workflow
- **GIVEN** workflow 文件位于 `/a/b/w.workflow.yaml`
- **WHEN** 某个 run 的 `demand` 为 `./x.demand.yaml`
- **THEN** 系统 MUST 加载 `/a/b/x.demand.yaml`

### Requirement: Workflow enforces failure_policy
系统 MUST 支持以下 `failure_policy`:
- `all_fail`(默认): 任一 run 失败即使 workflow 失败
- `primary_only`: 失败的 run 被跳过,后续 runs 继续执行;调用方必须可检查失败集合

#### Scenario: all_fail stops on first error
- **WHEN** `failure_policy=all_fail` 且某个 run 执行抛出异常
- **THEN** workflow MUST 失败并抛出包含该 run id 的错误
- **AND** workflow MUST 不再调度任何尚未开始的 runs

#### Scenario: primary_only continues and returns errors
- **WHEN** `failure_policy=primary_only` 且某个 run 失败
- **THEN** workflow MUST 继续执行后续 runs
- **AND** workflow 返回值 MUST 包含失败 run 的可检查错误信息(至少包含 run id 与 demand 路径)

### Requirement: max_concurrency limits parallel runs deterministically
系统 MUST 支持 `max_concurrency` 控制 runs 粒度并发上限,并确保返回结果顺序与 `workflow.runs` 声明顺序一致。
workflow 返回值 MUST 提供“按 runs 对齐”的结果集合:返回集合长度 MUST 等于 `workflow.runs` 长度,并包含每个 run 的 `id` 与 `demand` 路径,以便调用方可稳定对齐检查。

#### Scenario: results preserve declared order
- **WHEN** `max_concurrency>1` 导致 runs 并发执行
- **THEN** workflow 返回的结果集合顺序 MUST 与 `workflow.runs` 的声明顺序一致

### Requirement: share_preload_cache reuses preload_forever sources across runs
当 `share_preload_cache=true` 时,系统 MUST 在同一次 workflow 执行内跨 runs 共享 `cache_mode: preload_forever` 的预加载结果。
系统 MUST 确保同一 `source_id` 的 preload 结果最多加载一次并被复用。

#### Scenario: preload_forever is loaded once
- **GIVEN** 两个不同 run 的 demand 都包含 `sources.dim` 且 `cache_mode: preload_forever`
- **WHEN** workflow 执行且 `share_preload_cache=true`
- **THEN** `dim` loader MUST 在整个 workflow 中最多被调用一次

### Requirement: preload cache conflicts fail fast
当 `share_preload_cache=true` 时,系统 MUST 对同一 `source_id` 的 preload 规格执行一致性校验(至少包含 loader 引用与渲染后的 params 与 normalize 等关键字段)。
系统 MUST 在执行任一 run 之前完成上述一致性预检查(避免运行长时间后才因冲突失败)。
若不同 runs 中同一 `source_id` 的规格不一致,系统 MUST fail-fast 报错并指出冲突 runs 与差异字段。

#### Scenario: conflicting preload spec is rejected before execution
- **GIVEN** run A 的 `sources.dim.loader` 与 run B 的 `sources.dim.loader` 不同(或 params/normalize 不同)
- **WHEN** workflow 启动且 `share_preload_cache=true`
- **THEN** workflow MUST 报错并包含 run A/run B 的冲突信息
- **AND** workflow MUST 不执行任何 run
