# yaml-dsl-workflow Specification

**状态: ✅ 已实现**

## Purpose
提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/workflow.py` (workflow config 解析 + demand 路径解析)
- `src/IMPL_ROOT/dsl/by_yaml/workflow_entrypoints.py` (run_workflow 实现)
- `src/IMPL_ROOT/dsl/by_yaml/workflow_types.py` (workflow config 类型稳定导入路径)
- `src/IMPL_ROOT/dsl/by_yaml/workflow_paths.py` (workflow demand 路径解析稳定导入路径)
- `src/IMPL_ROOT/workflow/loaders.py` (workflow YAML 中可通过字符串引用的内置 loaders)
- `src/IMPL_ROOT/execution/workflow_cache_pool.py` (workflow-scope cache pool)
- `src/IMPL_ROOT/dsl/by_yaml/schema/workflow.gen.json` (workflow schema)
## Requirements
### Requirement: workflow public guidance MUST use curated stable entrypoints

在 workflow 分层稳定后，系统 MUST 将 workflow 的用户侧导入与示例统一收敛到 curated stable entrypoints。

系统 MUST 允许面向用户的 workflow 官方用法通过以下路径表达：

- `scalim.dsl.yaml_dsl.run_workflow`
- `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.yaml_dsl.workflow_paths`

系统 MUST NOT 再把 workflow 的内部实现路径写成官方用户导入路径。

#### Scenario: workflow examples use stable facade paths
- **WHEN** 维护者编写或更新 workflow 相关 examples、skills 与 gate
- **THEN** 这些材料 MUST 使用 curated stable entrypoints
- **AND** 不得把内部 workflow runtime 模块路径写成推荐用户路径

### Requirement: Workflow YAML declares runs and options
系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。
workflow MUST 包含:
- `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径,并支持可选的 `depends_on` 与 `init_vars`
- `workflow.options`: 运行选项,包含 `max_concurrency`、`failure_policy`、`cache_pool`(可选)、`ctx`(可选) 与 `resources_wait`(可选)

#### Scenario: workflow file passes schema validation
- **WHEN** workflow YAML 同时包含 `workflow.runs` 与 `workflow.options`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: resources_wait is allowed in workflow.options
- **GIVEN** workflow YAML 声明 `workflow.options.resources_wait`
- **WHEN** 运行 schema-only 校验
- **THEN** 校验 MUST 通过

### Requirement: workflow demand preloading MUST stay structural

workflow IR 编译阶段对 `workflow.runs[*].demand` 的预加载 MUST 仅服务于结构分析（例如 outputs/resources/dependency wiring），MUST NOT 在该阶段执行依赖 runtime diagnostics policy 的 demand 诊断。

#### Scenario: workflow IR compile accepts duplicate display names until runtime compile
- **GIVEN** 某个 workflow run 引用的 demand YAML 可以成功解析结构信息
- **AND** 该 demand 仅会在 `validate_unique_field_names=True` 时因 duplicate effective field display names 失败
- **WHEN** 系统执行 `compile_workflow_ir(...)`
- **THEN** workflow IR compile MUST 成功返回 demand-derived 结构信息
- **AND** 后续是否报 duplicate-name 错误 MUST 由具备 effective runtime policy 的边界决定（例如 workflow preflight 或 demand runtime compile）

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

### Requirement: workflow preflight errors MUST be treated as workflow config/compile errors (independent of failure_policy)
当某个诊断被定义为 workflow preflight（engine 启动前）失败时,系统 MUST 直接 raise 并中止整个 workflow,且 MUST NOT 继续调度其它 runs（`failure_policy` 不适用）:

- 系统 MUST 直接 raise 并中止整个 workflow
- 系统 MUST NOT 将该失败视为“某个 run 的可恢复失败”并继续调度其它 runs
- `failure_policy` MUST 不影响 preflight 的失败语义

#### Scenario: primary_only does not continue on preflight failure
- **GIVEN** workflow.options.failure_policy=primary_only
- **AND** preflight 发现某个 run 存在 duplicate effective field display names 且触发 `validate_unique_field_names`
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST 直接 raise 并中止整个 workflow
- **AND** workflow MUST NOT 执行任何 run

### Requirement: max_concurrency limits parallel runs deterministically
系统 MUST 支持 `max_concurrency` 控制 runs 粒度并发上限,并确保返回结果顺序与 `workflow.runs` 声明顺序一致。
workflow 返回值 MUST 提供“按 runs 对齐”的结果集合:返回集合长度 MUST 等于 `workflow.runs` 长度,并包含每个 run 的 `id` 与 `demand` 路径,以便调用方可稳定对齐检查。

#### Scenario: results preserve declared order
- **WHEN** `max_concurrency>1` 导致 runs 并发执行
- **THEN** workflow 返回的结果集合顺序 MUST 与 `workflow.runs` 的声明顺序一致

### Requirement: workflow nodes declare explicit DAG deps via `depends_on`
系统 MUST 扩展 workflow YAML,允许通过显式依赖声明表达节点之间的 DAG 关系:
- `workflow.runs[*].depends_on` MAY 存在且 MUST 为 run id 列表
- 系统 MUST 做静态校验:
  - 被引用的 run id MUST 存在
  - 图 MUST 无环(cycle detection)
  - 重复 deps MUST 被去重（保留首次出现的顺序）,不得影响确定性与可测试性

#### Scenario: dependent nodes start after prerequisites
- **GIVEN** workflow 中 node B 声明依赖 node A
- **WHEN** workflow 在并发模式下调度执行
- **THEN** 系统 MUST 在 node A 成功完成后才允许 node B 启动

#### Scenario: cycles are rejected before execution
- **GIVEN** workflow 中 A depends_on [B] 且 B depends_on [A]
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告可读的 cycle 路径（例如 `[A, B, A]`）

### Requirement: workflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)
系统 MUST 在一次 workflow 执行中维护一个 workflow-level ctx store,用于在依赖边上传递小体量上下文:
- ctx MUST 以 `workflow_node_id` 为命名空间(对 demand 节点等于 workflow YAML 的 `runs[*].id`)
- ctx 值 MUST 为 JSON-like 小对象(标量/小 list/dict),并设置大小护栏
- 系统 MUST 禁止将 rows/dataset/大型输出放入 ctx；大对象必须通过 artifacts/resources 路径表达
- ctx store MUST 线程安全(并发执行下可安全读写)

#### Scenario: ctx is only readable from dependency closure
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 尝试读取 `{$ctx: {node: A, key: output_path}}`
- **THEN** 系统 MUST fail-fast 并报告“ctx 引用超出 deps 可见范围”

### Requirement: ctx guardrails MUST be configurable via `workflow.options.ctx`
系统 MUST 提供 workflow-level ctx 护栏配置入口,并在超限时 fail-fast:

- `workflow.options.ctx` MAY 缺省（使用默认护栏）
- `workflow.options.ctx.max_value_bytes` MUST 为正整数（默认 65536）
- `workflow.options.ctx.max_bytes` MUST 为正整数（默认 1048576）

#### Scenario: ctx guardrails pass schema validation
- **WHEN** workflow YAML 包含 `workflow.options.ctx`
- **THEN** schema-only 校验 MUST 通过

### Requirement: demand nodes MUST publish a minimal default ctx summary
系统 MUST 为 demand 节点在完成时发布一组稳定的默认 ctx keys,用于减少 Python glue:
- `output_path`（字符串或 null；当无法推导/不适用时为 null）
- `total_rows`（整数或 null）
- `duration_secs`（浮点数；单位秒）

#### Scenario: downstream can consume default ctx keys
- **GIVEN** node B depends_on [A]
- **WHEN** node A 完成并发布默认 ctx summary
- **THEN** node B MUST 能通过 `{$ctx: {node: A, key: total_rows}}` 读取该值并注入其输入

### Requirement: `$ctx` directives are resolved during compile-on-ready materialization
系统 MUST 支持在 workflow YAML 的 `init_vars` 中引用上游 ctx,并在 node 就绪时渲染这些值:
- `{$ctx: {node: <upstream_node_id>, key: <ctx_key>}}` MUST 被视为指令节点(对象节点),而不是字符串插值
- `$ctx` 渲染 MUST 发生在 node 的“物化编译”阶段(compile-on-ready),以避免启动时 ctx 不可得的问题
- 渲染后的值 MUST 注入为 demand 编译期 `init_vars`,并复用既有 `{$init_var: ...}` 解析契约

#### Scenario: ctx-driven init_vars trigger compile-on-ready
- **GIVEN** node B depends_on [A]
- **AND** node B 声明 `init_vars: {x: {$ctx: {node: A, key: output_path}}}`
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 node A 完成并发布 ctx 后才物化编译 node B

### Requirement: failure propagation cancels downstream nodes deterministically
当 DAG 中上游失败/取消导致下游不可执行时,系统 MUST 以确定性方式取消这些下游 nodes:
- 若某 node 的任一 prerequisite 失败,该 node MUST NOT 执行
- 系统 MUST 将该 node 标记为 cancelled 并携带原因摘要(例如 dependency_failed)
- 在 `failure_policy=all_fail` 时,系统 MUST 取消所有未开始的 nodes,原因 MUST 为 `policy_all_fail`

#### Scenario: downstream nodes are cancelled on upstream failure
- **GIVEN** node B depends_on [A]
- **AND** node A 执行失败
- **WHEN** workflow 结束
- **THEN** node B MUST 以 cancelled 结束,且原因应指向上游依赖失败

### Requirement: workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
系统 MUST 将 workflow 的共享缓存配置入口收敛到结构化的 `workflow.options.cache_pool`,并移除 `workflow.options.share_preload_cache`.

#### Scenario: cache_pool config passes schema validation
- **WHEN** workflow YAML 包含 `workflow.options.cache_pool`
- **THEN** schema-only 校验 MUST 通过

#### Scenario: share_preload_cache is rejected
- **WHEN** workflow YAML 包含 `workflow.options.share_preload_cache`
- **THEN** 系统 MUST fail-fast 报错(提示迁移到 `workflow.options.cache_pool`)

NOTE: cache pool 的语义(冲突策略/生命周期/预算/可观测性)由 `workflow-cache-pool` 能力规范定义.

### Requirement: workflow entrypoints MUST be importable under Python 3.6
系统 MUST 保证在 Python 3.6 + `typing-extensions==4.1.1` 的最小依赖环境中, workflow 入口实现模块可被导入:

- `scalim.dsl.yaml_dsl.workflow_entrypoints`

系统 MUST 确保该 import 不依赖 `openpyxl`/`pandas` 等可选依赖。

#### Scenario: workflow_entrypoints imports in a minimal Py3.6 environment
- **GIVEN** 仅安装了 `PyYAML` 与 `typing-extensions==4.1.1` 的 Python 3.6 环境
- **WHEN** 执行 `python -c "from scalim.dsl.yaml_dsl import workflow_entrypoints"`
- **THEN** import MUST 成功

#### Scenario: optional dependencies remain optional for core imports
- **GIVEN** 环境中未安装 `openpyxl`
- **WHEN** 用户仅导入 Scalim 核心入口模块（包含 workflow 相关实现模块）
- **THEN** import MUST NOT 因 `openpyxl` 缺失而失败

### Requirement: workflow emits workflow-level events and injects attribution for demand events
workflow 执行 MUST 提供可观测性桥接层,用于将 per-demand 事件流稳定归因到 workflow YAML 的节点 id,并提供最小的 workflow-level 事件集合.

workflow MUST 生成一个 `workflow_exec_id` 并贯穿一次 workflow 调用的生命周期.

对每个 demand 节点,workflow MUST:
- 将 `workflow_exec_id` 与 `workflow_node_id` 注入到该 demand 事件流的 `Event.meta` 中
- 保持 demand 事件流的 `Event.run_id` 语义不变(仍为一次 demand 执行标识)

workflow 同时 MUST 发出最小集合的 workflow-level 事件:
- `workflow_node_start`
- `workflow_node_end`
- `workflow_node_cancelled`

对 workflow-level 事件:
- `Event.run_id` MUST 等于 `workflow_exec_id`(形成 workflow 事件流的稳定分区)
- `Event.seq` MUST 在该 `run_id` 内单调递增
- `Event.meta` MUST 同时包含 `workflow_exec_id` 与 `workflow_node_id`

#### Scenario: demand events can be joined back to workflow node ids
- **GIVEN** workflow YAML 声明 runs: A/B
- **WHEN** workflow 并发执行 A/B 两个 demand
- **THEN** A 的 demand 事件 `Event.meta.workflow_node_id` MUST 等于 `"A"`
- **AND** B 的 demand 事件 `Event.meta.workflow_node_id` MUST 等于 `"B"`
- **AND** A/B 的 `Event.meta.workflow_exec_id` MUST 相同(同一次 workflow 执行)

#### Scenario: workflow-level events have workflow_exec_id run partition
- **WHEN** workflow 调度开始/结束/取消某个节点
- **THEN** 对应的 workflow-level 事件 `Event.run_id` MUST 等于 `workflow_exec_id`
- **AND** `Event.meta` MUST 包含 `workflow_exec_id` 与 `workflow_node_id`

### Requirement: max_concurrency>1 requires thread-safe or stateless components
当 workflow 的 `max_concurrency>1` 时,系统 MUST 明确同一 `components` 列表中的 hook/observer 实例可能被多个并发节点复用的运行时契约:
- `max_concurrency>1` 时,components MUST 为线程安全或无状态
- 否则行为未定义且不保证正确性;调用方 SHOULD 将 `max_concurrency` 降为 1

#### Scenario: documentation makes component concurrency contract explicit
- **WHEN** 用户开启 `max_concurrency>1`
- **THEN** 系统规范 MUST 明确 components 的线程安全/无状态要求

### Requirement: workflow YAML MUST use `workflow.resources.books` and MUST reject `writes` authoring surface
系统 MUST 将 workflow YAML 的共享输出资源入口收敛为 `workflow.resources.books`,并将已移除的 workflow-level 写入 intents 字段视为非法输入:

- `workflow.resources.books` MAY 存在且 MUST 为 mapping
- 已移除的 workflow-level 写入 intents 字段出现时 MUST fail-fast 并给出迁移提示(迁移到 demand outputs 的 `to/write`)

#### Scenario: workflow YAML rejects removed writes field
- **GIVEN** workflow YAML 某个 run 包含 `writes: [...]`
- **WHEN** workflow 被解析/校验/编译
- **THEN** 系统 MUST fail-fast 并指出“已移除的 workflow-level 写入 intents 字段”

### Requirement: workflow.options.resources_wait MUST configure join/wait diagnostics and timeout
系统 MUST 扩展 workflow YAML 的 `workflow.options` 支持结构化的 `resources_wait` 配置,作为 inflight join/wait 的 SSOT:

- `workflow.options.resources_wait.max_wait_s` MUST 为有限正数值(秒),缺省时 MUST 等价于 600
- `workflow.options.resources_wait.diagnostics` MAY 缺省;若提供,MUST 为 mapping
  - `diagnostics.enabled` MUST 为 bool(缺省等价于 false)
  - `diagnostics.warn_after_s` MUST 为有限非负数值(秒)(缺省等价于 30)
  - `diagnostics.repeat_every_s` MAY 缺省;若提供,MUST 为有限正数(秒)
  - `diagnostics.capture_owner_callsite` MAY 缺省;若提供,MUST 为 bool
- 该配置 MUST 纳入 schema-only 校验并在解析失败时 fail-fast

#### Scenario: resources_wait passes schema validation
- **WHEN** workflow YAML 声明 `workflow.options.resources_wait` 且字段类型合法
- **THEN** schema-only 校验 MUST 通过

### Requirement: workflow.options.output_staging MUST configure staging directory and cleanup policy
系统 MUST 扩展 workflow YAML 的 `workflow.options` 支持结构化的 `output_staging` 配置,作为共享输出 staging/publish 行为的 SSOT:

- `workflow.options.output_staging.dir_name` MUST 为非空字符串且不包含路径分隔符(`/`或`\`);缺省时 MUST 等价于 `.scalim-staging`
- `workflow.options.output_staging.keep_on_success` MUST 为 bool;缺省时 MUST 等价于 `false`
- `workflow.options.output_staging.keep_on_failure` MUST 为 bool;缺省时 MUST 等价于 `true`
- 该配置 MUST 纳入 schema-only 校验并在解析失败时 fail-fast

#### Scenario: output_staging passes schema validation
- **WHEN** workflow YAML 声明 `workflow.options.output_staging` 且字段类型合法
- **THEN** schema-only 校验 MUST 通过

### Requirement: `run_workflow(...)` MUST orchestrate parse/preload/effective-merge/preflight via a single lifecycle SSOT
为避免出现“多入口各自拼装生命周期”导致的 drift 与 workaround 修复点扩散，系统 MUST 将 workflow 生命周期的编排收敛为单一 SSOT（lifecycle pipeline），并要求 `run_workflow(...)` 复用该 SSOT：

- `run_workflow(...)` MUST 以 phase pipeline 的顺序执行关键阶段：parse、structural preload、effective merge、preflight、execute
- `run_workflow(...)` MUST NOT 跳过 preflight 直接启动 engine

#### Scenario: workflow execution always runs preflight before engine scheduling
- **GIVEN** workflow 存在某个可推理的 preflight 失败
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST 在 engine 启动前直接 raise
- **AND** workflow engine MUST NOT 被启动

