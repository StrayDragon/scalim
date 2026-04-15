## Context

workflow YAML 的初衷是作为“可审阅、可版本化”的编排 SSOT（DAG + resources + per-run 引用），但当前仍允许在 `workflow.options` 中写入一组与环境、性能预算与发布策略强绑定的 knobs：

- `max_concurrency`：线程池并发度（开发/CI/生产通常不同）
- `failure_policy`：失败传播与跳过策略（不同环境可能需要不同容错/调试体验）
- `ctx`：workflow ctx store 的大小护栏（不同环境可能需要不同内存预算）
- `cache_pool`：共享缓存池的冲突策略、释放策略与预算（不同环境往往需要不同内存预算）

这会迫使调用方在“YAML 之外”引入 override/复制 YAML/环境分支等机制来覆盖这些字段，形成：
- YAML 不再是 SSOT（同一 DAG 在不同环境有多份近似但不一致的 authoring）
- 覆盖逻辑分散在 glue code/CI 脚本中，反馈链路长且难以审阅

仓库内已经存在“runtime policy boundary”的先例：workflow 的 `resources_wait` / `output_staging` 已迁出 YAML（只能通过运行入口配置）；demand 侧也已把多个 runtime knobs 迁出 YAML 主线并收敛到 typed `RunOptions`。

本变更将把 workflow 剩余的环境敏感 knobs 也迁出 YAML，统一到 Python/CLI runtime entrypoints 的 typed surface。

相关实现锚点（当前状态）：
- YAML 解析：`src/scalim/dsl/yaml_dsl/workflow_config/_parse.py#L1`
- workflow IR 编译：`src/scalim/dsl/yaml_dsl/workflow_compile.py#L1`
- 执行器读取 `workflow_ir.options.*`：`src/scalim/workflow/execute.py#L1`

文档/生成边界（实现时必须遵守）：
- `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 为生成物；禁止手改，需通过 `just gen-yaml-dsl-schema` 更新。
- agent skill references（如 `artifacts/**/syntax-catalog.gen.md`、`references/generated/*.gen.md`）为生成物；需通过 `just gen-agent-skill` 更新。
- docs 注入区块必须通过 `just gen-docs` 更新；`just qa`/drift checks 兜底。

当前 workflow YAML 参数盘点（以 parser 行为为准）：
- **`workflow.runs`（必填，非空列表）**
  - `id`（必填，非空字符串；唯一；禁止保留前缀）
  - `demand`（必填，非空字符串；相对路径基于 workflow 文件）
  - `depends_on`（可选，list[str]；去重但保留顺序）
  - `init_vars`（可选，mapping[str, any]；允许 JSON-like；`$ctx` 指令在运行期渲染）
  - `main_rows_from`（可选，mapping；当前仅支持 `{run: <run_id>}`）
  - 已移除：`deps`（改为 `depends_on`）、`write_to`、`writes`
- **`workflow.options`（可选，mapping）**
  - 当前允许：`max_concurrency` / `failure_policy` / `ctx` / `cache_pool`
  - 已移出 YAML：`resources_wait` / `output_staging`（仅能通过 runtime entrypoints 配置）
  - 已移除：`share_preload_cache`（迁移到 `cache_pool`）

## Goals / Non-Goals

**Goals:**
- 将 workflow YAML 中的 `workflow.options.*` runtime knobs 迁出主线 authoring surface：`max_concurrency` / `failure_policy` / `cache_pool`。
- `workflow.options.ctx` 护栏将被移除：框架不再对 `$ctx` payload 做 size-limit 报错（仅保留 JSON-like 校验与依赖可见性校验）。
- 提供 workflow-level runtime entrypoints 的 typed surface，使调用方可在 Python/CLI 侧按环境注入核心编排 knobs（目标是最小集合：`max_concurrency` / `failure_policy`），并为后续 c5 的 scheduling preset 预留可演进的组织结构。
- workflow YAML schema-only 校验在迁出后仍保持“只校验 YAML 主线”的清晰边界：迁出的字段出现时 fail-fast 并给出迁移指引。
- 维持稳定默认行为：调用方不显式传入 runtime options 时，运行行为与历史默认值等价（例如并发度默认 1、失败策略默认 `all_fail`、cache_pool 默认关闭）。

**Non-Goals:**
- 不在本变更中引入新的 DAG 调度语义（例如 wave barrier / phase scheduling）；该话题作为独立能力讨论。
- 不改变 `failure_policy` 的核心语义；`cache_pool` 的核心复用/诊断行为保持一致，但对外配置面收口为 preset（仅允许最少 knobs）。
- 不在框架内部做“按环境自动选择策略”的魔法（环境选择由调用方/集成层负责，框架只提供 typed knobs）。
- 不提供框架内置的“effective workflow runtime options”可观测输出（如需要，由集成方在 Python 侧自行记录/输出）。

## Decisions

### 1) 迁出字段采用“拒绝 + 迁移指引”，不做 YAML 兼容层

按仓库迭代规则：除非调用方明确要求兼容旧写法，否则直接升级为新写法（拒绝旧字段），避免长期双写与语义分叉。

设计要点：
- workflow YAML 若出现 `workflow.options`（或其子字段），解析阶段直接报错（fail-fast），并提示迁移到 runtime entrypoints。
- 错误信息必须指向新的 runtime entrypoints（例如 `run_workflow(..., workflow_runtime=...)` 或等价接口），并说明默认行为与迁移方式。

### 2) 新增 `workflow_runtime` typed surface（Python；非大平铺；支持 preset 工厂方法）

在稳定导入路径下提供一个 workflow-level runtime options 类型（建议新增到 `scalim.dsl.yaml_dsl.workflow_types` 并 re-export 到 facade），并在 `run_workflow(...)` 增加一个新的入口参数 `workflow_runtime=...`。

设计约束：
- **接口受限**：避免把运行期策略散落成多个顶层 kwargs，也避免“字符串 + 多散字段”的自由组合。
- **正交组织**：将不同策略/配置拆分为内聚的小数据类（execution/cache/scheduler/…），避免未来 knobs 增长导致大平铺难维护。
- **鼓励 preset**：对外提供 classmethod factory（例如 `WorkflowRuntimeOptions.preset_default()` / `WorkflowCachePoolPreloadForeverShared(...)`），引导用户优先使用稳定预设而非自行拼装细节。

建议结构（示意，字段名可调整）：
- `WorkflowRuntimeOptions.execution`: `WorkflowExecutionOptions(max_concurrency, failure_policy)`
- `WorkflowRuntimeOptions.cache_pool`: `WorkflowCachePoolPreset`（封闭集合；仅最小使用场景）
- `WorkflowRuntimeOptions.resources_wait`: `WorkflowResourcesWaitOptions`
- `WorkflowRuntimeOptions.output_staging`: `WorkflowOutputStagingOptions`
- `WorkflowRuntimeOptions.scheduler`: 预留给 c5（pipeline / wave_barrier）的调度策略配置（默认 pipeline；本变更不引入新语义，但为后续演进预留位置以减少 API churn）

其中 `resources_wait` / `output_staging` 的语义（用于解释“它是干啥的”）：
- `resources_wait`：当 workflow node 需要的资源（resources tokens/locks）暂不可用时，scheduler 在放弃前最多等待多久，并可按需开启诊断日志（默认 `max_wait_s=600` 且 diagnostics 关闭）。
- `output_staging`：对 workflow node 的输出做一次“落盘暂存”以增强鲁棒性与可排障性，并在成功/失败后按策略清理暂存目录（默认目录名 `.scalim-staging`，失败保留、成功清理）。

其中 `WorkflowExecutionOptions` 目标仅包含：
- `max_concurrency: int`（>=1）
- `failure_policy: str`（例如 `all_fail` / `primary_only`，以现有枚举为准）

运行入口形态（示意）：
- 旧：`run_workflow(..., workflow_resources_wait=..., workflow_output_staging=..., ...)`
- 新：`run_workflow(..., workflow_runtime=WorkflowRuntimeOptions(...), ...)`

并在编译 workflow IR 前将 `workflow_runtime` 注入到 IR 的 options（编译产物仍落入 `WorkflowOptionsIr`，以最大化复用现有执行路径）。

Python 3.6 兼容性约束：
- `src/scalim/` 运行时仍需兼容 Python 3.6：不使用 `X | Y`、`list[T]` 等新语法；必要时使用 `typing`/`typing_extensions` 兼容层。

### 3) 移除 `$ctx` store 护栏（不对外暴露，也不保留内置限制）

`$ctx` 是 workflow 节点间传递“可序列化摘要信息”的机制。ctx store 护栏的存在主要用于防止单节点发布过大 payload 或在大 DAG 下累积占用不可控内存。

本变更的取舍：
- **移除 ctx store 护栏逻辑本身**：不再对单值/总量做 size-limit 报错（框架处理了也只能报错，无法真正治理；应交由调用方在业务侧做 payload 治理/观测）。
- 移除 `workflow.options.ctx` 作为 authoring/runtime 配置入口（同时也避免引入几乎无人使用但成本很高的可配置面）。
- 保留 `$ctx` 的结构性校验：JSON-like 校验 + visibility(必须显式 `depends_on`) 校验。

### 4) `cache_pool` 从 core options 中拆出（保持内聚；避免跨字段耦合）

`cache_pool` 是相对“重”的能力：涉及预算、冲突策略与生命周期策略。它不应该与核心编排 knobs（并发/失败策略）被迫共处一个扁平 options 结构中。

建议：
- 将 `cache_pool` 迁出 workflow YAML
- 在 `workflow_runtime` 内以 **preset + 极小 knobs** 的形式注入，并与 `execution/resources_wait/output_staging/scheduler` 等保持正交（避免对外接口过度开放）
- `cache_pool` 的内部实现仍保留现有的 signature/冲突策略/生命周期/预算/事件机制，但对外配置面 **不再暴露** 全量细节字段（避免“外部接口太开放 → core 框架维护复杂度上升”）

#### cache_pool 的现有使用场景（当前主要用于 `preload_forever`）

`workflow-cache-pool` 的核心价值是：**同一次 workflow 执行内跨 nodes 复用“可共享的 preload 结果”**，并且用 signature/冲突策略/生命周期/预算/事件把“复用正确性与可诊断性”做成框架能力。

现状（实现与 spec 一致）：
- **作用域**：workflow-scope（一次 workflow 执行），不是全局进程级缓存。
- **当前主要覆盖点**：pipeline 的 `preload_forever`（见 `src/scalim/execution/pipeline/base/pipeline.py`），当多个 workflow node 使用同一个 source loader 且渲染后的 params 等一致时，只加载一次，其余 node 直接复用。
- **signature（复用正确性）**：以 `(kind, source_id)` 为逻辑 key，但会把 `loader_ref`、`rendered_params`、normalize/key/lookup_cast 等纳入 signature（见 `src/scalim/execution/workflow_cache_pool.py::WorkflowCacheEntrySignature`），避免“同名 source_id 但实际加载条件不同”导致错复用。
- **冲突策略（可诊断性）**：当同一 `(kind, source_id)` 观察到不同 signature 时，按 `conflict_policy=error|warn|separate` 处理（默认严格 error）。
- **生命周期（减少常驻内存）**：`release_policy=dag_refcount|workflow_end`，并基于 DAG 推导 consumer 上界做 refcount；支持 `pin` 禁止被释放/淘汰。
- **预算（避免 OOM/无界增长）**：`budget.max_entries` + `over_budget_policy=fail_fast|evict_lru`（仅逐出 idle 且非 pin 的 entry）。
- **观测事件**：`workflow_cache_acquire/release/evict` + 冲突 warning，用于 hooks/observers/viz 解释“为什么它没重复加载/为什么它被释放/为什么冲突失败”等。

典型业务场景：
- 多个 run 共享同一份“维表/映射字典/配置快照/索引工件”，而该 preload 代价显著（网络/IO/CPU）。
- 同一 workflow 中重复跑多个变体 demand，但它们引用同一个昂贵的 preload 构造（例如构建 lookup index、加载大模型/大词表、拉取远端 token/配置并解析）。

不需要 cache_pool 的场景：
- preload 很轻；或 workflow node 数量少；或 loader 本身已有可靠的进程级缓存（且能接受其生命周期/内存占用）。

本变更（c0）的定位：
- `cache_pool` 配置迁出 YAML，并基于真实用户案例决定“保留但收口”为 runtime-only preset（而不是继续暴露扁平/全量 knobs）。

#### 对外接口：runtime-only preset（收口方案）

动机：真实 workflow（例如 `cus_collect_infos.workflow.yaml`）在多 demand 复用 `cache_mode: preload_forever` source，确实能受益于 workflow-scope cache 复用；因此不建议直接移除能力。但对外配置面必须受限，只提供可维护的 preset。

建议对外暴露一个 **封闭集合** 的 cache preset（示意）：
- `WorkflowCachePoolDisabled()`（默认）：关闭 cache_pool（保持历史“未配置即关闭”的默认行为）。
- `WorkflowCachePoolPreloadForeverShared(max_entries=16)`：启用跨 nodes 的 `preload_forever` 共享（当前唯一支持的 kind）。

其中 `WorkflowCachePoolPreloadForeverShared` 仅允许极少 knobs：
- `max_entries`（预算上限，>=1；默认 `16`）：限制“同一次 workflow 执行内最多保留多少个 cache entry（按 signature 计数，不是按 bytes）”，用于在不同环境/内存预算下调参。

其余策略固定为稳定默认（不开放给外部）：
- `conflict_policy=error`（严格正确性）
- `release_policy=dag_refcount`（尽早释放，减少常驻内存）
- `over_budget_policy=fail_fast`（超限即失败，避免隐式逐出导致行为难解释）
- `pin=()`（暂不对外暴露；如出现明确需求，再以新增 preset 的方式扩展）

迁移示意（示意 API，字段名最终以实现为准）：
- YAML（旧）：
  - `workflow.options.cache_pool.budget.max_entries: 16`
- Python（新）：
  - `run_workflow(..., workflow_runtime=WorkflowRuntimeOptions(cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16)))`

### 5) workflow IR 编译阶段接收 runtime options，并写入 IR（保持执行器 API 不变）

当前执行器从 `workflow_ir.options.*` 读取并发/失败策略/cache_pool。为了减少扩散与重构成本，本变更选择：
- 在 workflow compile/preload 阶段将 runtime options 写入 `workflow_ir.options`（来源变更但 IR 形状不变）
- 执行阶段继续消费 `workflow_ir.options`，无需改变 scheduler/controller 的主要结构

### 6) YAML 主线保留的字段范围

本变更后 workflow YAML 主线仅保留结构性编排信息：
- `workflow.runs`（DAG 结构与 per-run 引用）
- `workflow.resources`（资源定义）

`workflow.options` 将被视为 runtime policy（与 demand runtime policy 一致），不再作为 YAML authoring surface。

## Risks / Trade-offs

- [BREAKING: 现有 YAML 失效] → 通过清晰的 fail-fast 错误信息 + 文档示例 + 生成 references 同步更新降低迁移成本。
- [并发度不再可从 YAML 静态审阅] → 在用户侧 guidance 中强调：并发度来自 runtime entrypoints；建议集成层把环境策略放入可审阅的 Python 配置模块/SSOT（而不是散落脚本）。
- [cache_pool 迁出后，YAML 无法展示内存预算] → 这是刻意选择：预算属于 control-plane；通过 runtime policy 的 typed 配置集中管理。

## Migration Plan

- 对每个 workflow YAML：
  - 删除 `workflow.options`（或至少删除 `workflow.options.*` 下所有 runtime knobs）。
  - 在调用 `run_workflow(...)` 的 Python/CLI 集成处用 `workflow_runtime=...` 注入等价的 runtime policy（默认值不需要显式传入）。
- 运行生成与门禁：
  - `just gen-yaml-dsl-schema`（更新 schema 生成物）
  - `just gen-agent-skill`（更新 syntax catalog / CLI-LSP references）
  - `just qa`（漂移与回归门禁）

## Open Questions

- (none)
