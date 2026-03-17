# yaml-dsl-workflow Specification

**状态: ✅ 已实现**

## Purpose
提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/workflow.py` (workflow config 解析 + demand 路径解析)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/workflow_entrypoints.py` (run_workflow 实现)
- `src/IMPL_ROOT/execution/workflow_cache_pool.py` (workflow-scope cache pool)
- `src/IMPL_ROOT/dsl/by_yaml/schema/workflow.gen.json` (workflow schema)

## Requirements

### Requirement: Workflow YAML declares runs and options
系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。
workflow MUST 包含:
- `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径
- `workflow.options`: 运行选项,包含 `max_concurrency`、`failure_policy`、`cache_pool`(可选)

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

- `scalim.dsl.by_yaml.runtime.workflow_entrypoints`

系统 MUST 确保该 import 不依赖 `openpyxl`/`pandas` 等可选依赖。

#### Scenario: workflow_entrypoints imports in a minimal Py3.6 environment
- **GIVEN** 仅安装了 `PyYAML` 与 `typing-extensions==4.1.1` 的 Python 3.6 环境
- **WHEN** 执行 `python -c "from scalim.dsl.by_yaml.runtime import workflow_entrypoints"`
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
