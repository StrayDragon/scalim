---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate yaml-dsl-workflow --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "yaml-dsl-workflow"
purpose: "提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目)."
requirements[22]{req_id,title,statement}:
  r1,workflow public guidance MUST use curated stable entrypoints,"在 workflow 分层稳定后，系统 MUST 将 workflow 的用户侧导入与示例统一收敛到 curated stable entrypoints。 系统 MUST 允许面向用户的 workflow 官方用法通过以下路径表达： - `scalim.dsl.yaml_dsl.run_workflow` - `scalim.dsl.yaml_dsl.workflow` - `scalim.dsl.yaml_dsl.workflow_types` - `scalim.dsl.yaml_dsl.workflow_paths` 系统 MUST NOT 再把 workflow 的内部实现路径写成官方用户导入路径。"
  r2,Workflow YAML declares runs and options,"系统 MUST 支持一种独立于 demand 的 workflow YAML 语法,用于声明多个 demand 的编排执行。 workflow MUST 包含: - `workflow.runs`: run 列表,每项包含 `id` 与 `demand` 路径,并支持可选的 `depends_on` 与 `init_vars` - `workflow.resources`: 可选的共享资源定义（例如 books 等） - `workflow.options` MUST NOT 出现在 YAML authoring surface（runtime policy boundary; 详见 `yaml-dsl-runtime-policy-boundary`）。"
  r3,workflow demand preloading MUST stay structural,"workflow IR 编译阶段对 `workflow.runs[*].demand` 的预加载 MUST 仅服务于结构分析（例如 outputs/resources/dependency wiring），MUST NOT 在该阶段执行依赖 runtime diagnostics policy 的 demand 诊断。"
  r4,Runs execute demand YAML via existing compilation pipeline,"系统 MUST 对每个 run 的 `demand` 路径加载并编译 demand YAML,并复用现有 demand 执行链路运行得到结果。 系统 MUST 以 workflow 文件所在目录作为相对路径基准。"
  r5,Workflow enforces failure_policy,"系统 MUST 支持以下 `failure_policy`: - `all_fail`(默认): 任一 run 失败即使 workflow 失败 - `primary_only`: 失败的 run 被跳过,后续 runs 继续执行;调用方必须可检查失败集合"
  r6,workflow preflight errors MUST be treated as workflow config/compile errors (ind,"当某个诊断被定义为 workflow preflight（engine 启动前）失败时,系统 MUST 直接 raise 并中止整个 workflow,且 MUST NOT 继续调度其它 runs（`failure_policy` 不适用）: - 系统 MUST 直接 raise 并中止整个 workflow - 系统 MUST NOT 将该失败视为“某个 run 的可恢复失败”并继续调度其它 runs - `failure_policy` MUST 不影响 preflight 的失败语义"
  r7,max_concurrency limits parallel runs deterministically,"系统 MUST 支持 `max_concurrency` 控制 runs 粒度并发上限,并确保返回结果顺序与 `workflow.runs` 声明顺序一致。 workflow 返回值 MUST 提供“按 runs 对齐”的结果集合:返回集合长度 MUST 等于 `workflow.runs` 长度,并包含每个 run 的 `id` 与 `demand` 路径,以便调用方可稳定对齐检查。"
  r8,workflow nodes declare explicit DAG deps via `depends_on`,"系统 MUST 扩展 workflow YAML,允许通过显式依赖声明表达节点之间的 DAG 关系: - `workflow.runs[*].depends_on` MAY 存在且 MUST 为 run id 列表 - 系统 MUST 做静态校验: - 被引用的 run id MUST 存在 - 图 MUST 无环(cycle detection) - 重复 deps MUST 被去重（保留首次出现的顺序）,不得影响确定性与可测试性"
  r9,"workflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)","系统 MUST 在一次 workflow 执行中维护一个 workflow-level ctx store,用于在依赖边上传递小体量上下文: - ctx MUST 以 `workflow_node_id` 为命名空间(对 demand 节点等于 workflow YAML 的 `runs[*].id`) - ctx 值 MUST 为 JSON-like 对象(标量/小 list/dict) - 框架 MUST NOT 对 ctx payload 施加 size-limit 护栏（不得因 payload 大小 fail-fast；payload 治理由调用方负责） - 系统 MUST 禁止将 rows/dataset/大型输出放入 ctx；大对象必须通过 artifacts/resources 路径表达 - ctx store MUST 线程安全(并发执行下可安全读写)"
  r10,demand nodes MUST publish a minimal default ctx summary,"系统 MUST 为 demand 节点在完成时发布一组稳定的默认 ctx keys,用于减少 Python glue: - `output_path`（字符串或 null；当无法推导/不适用时为 null） - `total_rows`（整数或 null） - `duration_secs`（浮点数；单位秒）"
  r11,"`$ctx` directives are resolved during compile-on-ready materialization","系统 MUST 支持在 workflow YAML 的 `init_vars` 中引用上游 ctx,并在 node 就绪时渲染这些值: - `{$ctx: {node: <upstream_node_id>, key: <ctx_key>}}` MUST 被视为指令节点(对象节点),而不是字符串插值 - `$ctx` 渲染 MUST 发生在 node 的“物化编译”阶段(compile-on-ready),以避免启动时 ctx 不可得的问题 - 渲染后的值 MUST 注入为 demand 编译期 `init_vars`,并复用既有 `{$init_var: ...}` 解析契约"
  r12,failure propagation cancels downstream nodes deterministically,"当 DAG 中上游失败/取消导致下游不可执行时,系统 MUST 以确定性方式取消这些下游 nodes: - 若某 node 的任一 prerequisite 失败,该 node MUST NOT 执行 - 系统 MUST 将该 node 标记为 cancelled 并携带原因摘要(例如 dependency_failed) - 在 `failure_policy=all_fail` 时,系统 MUST 取消所有未开始的 nodes,原因 MUST 为 `policy_all_fail`"
  r13,workflow options expose a stable `cache_pool` configuration (replacing `share_pr,"系统 MUST 提供 workflow-scope cache pool 能力以支持跨 nodes 复用（例如 `preload_forever`）；但 cache pool 的配置入口 MUST 位于 runtime policy boundary 并保持对外接口受限： - workflow YAML MUST NOT 再接受 `workflow.options.cache_pool`（出现时 MUST fail-fast，并指向 runtime entrypoints） - cache_pool 的可用配置 MUST 以封闭集合的 preset 方式提供（避免自由组合 knobs 导致维护成本上升） - 旧字段 `workflow.options.share_preload_cache` MUST 继续被拒绝，并给出迁移到 runtime preset 的提示"
  r14,workflow entrypoints MUST be importable under Python 3.6,"系统 MUST 保证在 Python 3.6 + `typing-extensions==4.1.1` 的最小依赖环境中, workflow 入口实现模块可被导入: - `scalim.dsl.yaml_dsl.workflow_entrypoints` 系统 MUST 确保该 import 不依赖 `openpyxl`/`pandas` 等可选依赖。"
  r15,"workflow emits workflow-level events and injects attribution for demand events","workflow 执行 MUST 提供可观测性桥接层,用于将 per-demand 事件流稳定归因到 workflow YAML 的节点 id,并提供最小的 workflow-level 事件集合. workflow MUST 生成一个 `workflow_exec_id` 并贯穿一次 workflow 调用的生命周期. 对每个 demand 节点,workflow MUST: - 将 `workflow_exec_id` 与 `workflow_node_id` 注入到该 demand 事件流的 `Event.meta` 中 - 保持 demand 事件流的 `Event.run_id` 语义不变(仍为一次 demand 执行标识) workflow 同时 MUST 发出最小集合的 workflow-level 事件: - `workflow_node_start` - `workflow_node_end` - `workflow_node_cancelled` 对 workflow-level 事件: - `Event.run_id` MUST 等于 `workflow_exec_id`(形成 workflow 事件流的稳定分区) - `Event.seq` MUST 在该 `run_id` 内单调递增 - `Event.meta` MUST 同时包含 `workflow_exec_id` 与 `workflow_node_id` - workflow node 事件 payload MUST 增量暴露以下字段,用于解释执行顺序（详见 `workflow-stage-scheduling`）: - `schedule_mode`（例如 `pipeline` / `stage_barrier`） - `stage`（节点阶段归因）"
  r16,"max_concurrency>1 requires thread-safe or stateless components","当 workflow 的 `max_concurrency>1` 时,系统 MUST 明确同一 `components` 列表中的 hook/observer 实例可能被多个并发节点复用的运行时契约: - `max_concurrency>1` 时,components MUST 为线程安全或无状态 - 否则行为未定义且不保证正确性;调用方 SHOULD 将 `max_concurrency` 降为 1"
  r17,workflow YAML MUST use `workflow.resources.books` and MUST reject `writes` autho,"系统 MUST 将 workflow YAML 的共享输出资源入口收敛为 `workflow.resources.books`,并将已移除的 workflow-level 写入 intents 字段视为非法输入: - `workflow.resources.books` MAY 存在且 MUST 为 mapping - 已移除的 workflow-level 写入 intents 字段出现时 MUST fail-fast 并给出迁移提示(迁移到 demand outputs 的 `to/write`)"
  r18,workflow.options.resources_wait MUST configure join/wait diagnostics and timeout,"系统 MUST 提供 workflow-level 的 resources wait 配置,作为 inflight join/wait 的 SSOT；该配置属于 runtime policy boundary： - workflow YAML MUST NOT 再接受 `workflow.options.resources_wait`（出现时 MUST fail-fast，并指向 runtime entrypoints） - runtime entrypoints MUST 允许通过 `workflow_runtime_options.resources_wait`（或等价 typed surface）配置以下字段： - `max_wait_s` MUST 为有限正数值(秒),缺省时 MUST 等价于 600 - `diagnostics` MAY 缺省;若提供,MUST 为 mapping - `diagnostics.enabled` MUST 为 bool(缺省等价于 false) - `diagnostics.warn_after_s` MUST 为有限非负数值(秒)(缺省等价于 30) - `diagnostics.repeat_every_s` MAY 缺省;若提供,MUST 为有限正数(秒) - `diagnostics.capture_owner_callsite` MAY 缺省;若提供,MUST 为 bool"
  r19,workflow.options.output_staging MUST configure staging directory and cleanup pol,"系统 MUST 提供 workflow-level 的 output staging 配置,作为共享输出 staging/publish 行为的 SSOT；该配置属于 runtime policy boundary： - workflow YAML MUST NOT 再接受 `workflow.options.output_staging`（出现时 MUST fail-fast，并指向 runtime entrypoints） - runtime entrypoints MUST 允许通过 `workflow_runtime_options.output_staging`（或等价 typed surface）配置以下字段： - `dir_name` MUST 为非空字符串且不包含路径分隔符(`/`或`\\`);缺省时 MUST 等价于 `.scalim-staging` - `keep_on_success` MUST 为 bool;缺省时 MUST 等价于 `false` - `keep_on_failure` MUST 为 bool;缺省时 MUST 等价于 `true`"
  r20,workflow scheduler preset MUST be configured through runtime entrypoints,"系统 MUST 允许调用方通过运行入口（runtime entrypoints）配置 workflow 的 scheduler preset（而不是通过 YAML authoring surface）： - workflow YAML MUST NOT 新增任何与 scheduler 相关的 authoring 字段 - runtime entrypoints MUST 允许通过 `workflow_runtime_options.scheduler`（或等价 typed surface）提供 scheduler preset - 当调用方未显式提供 scheduler preset 时,默认值 MUST 等价于 `pipeline`"
  r21,yaml_dsl public facade MUST export scheduler preset types under a stable import,"系统 MUST 在稳定导入路径上暴露 workflow scheduler preset 的类型,以便调用方以最小成本配置: - `scalim.dsl.yaml_dsl.workflow_types` MUST 导出 `PipelineSchedulerOptions` - `scalim.dsl.yaml_dsl.workflow_types` MUST 导出 `StageBarrierSchedulerOptions`"
  r22,"`run_workflow(...)` MUST orchestrate parse/preload/effective-merge/preflight via","为避免出现“多入口各自拼装生命周期”导致的 drift 与 workaround 修复点扩散，系统 MUST 将 workflow 生命周期的编排收敛为单一 SSOT（lifecycle pipeline），并要求 `run_workflow(...)` 复用该 SSOT： - `run_workflow(...)` MUST 以 phase pipeline 的顺序执行关键阶段：parse、structural preload、effective merge、preflight、execute - `run_workflow(...)` MUST NOT 跳过 preflight 直接启动 engine"
scenarios[50]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"workflow-examples-use-stable-facade-paths","",维护者编写或更新 workflow 相关 examples、skills 与 gate,这些材料 MUST 使用 curated stable entrypoints
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"workflow-file-passes-schema-validation","",workflow YAML 包含 `workflow.runs`（可选包含 `workflow.resources`）,"schema-only 校验 MUST 通过"
  r2,"resources-wait-in-workflow-options-is-rejected",workflow YAML 声明 `workflow.options.resources_wait`,用户执行 workflow validate 或运行入口解析,"系统 MUST fail-fast"
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"workflow-ir-compile-accepts-duplicate-display-names-until-ru",某个 workflow run 引用的 demand YAML 可以成功解析结构信息,系统执行 `compile_workflow_ir(...)`,"workflow IR compile MUST 成功返回 demand-derived 结构信息"
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"demand-path-is-resolved-relative-to-workflow",workflow 文件位于 `/a/b/w.workflow.yaml`,某个 run 的 `demand` 为 `./x.demand.yaml`,系统 MUST 加载 `/a/b/x.demand.yaml`
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,"all-fail-stops-on-first-error","",`failure_policy=all_fail` 且某个 run 执行抛出异常,workflow MUST 失败并抛出包含该 run id 的错误
  r5,"primary-only-continues-and-returns-errors","",`failure_policy=primary_only` 且某个 run 失败,workflow MUST 继续执行后续 runs
  r6,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r6,"primary-only-does-not-continue-on-preflight-failure",workflow.options.failure_policy=primary_only,用户调用 `run_workflow(...)`,系统 MUST 直接 raise 并中止整个 workflow
  r7,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r7,"results-preserve-declared-order","",`max_concurrency>1` 导致 runs 并发执行,workflow 返回的结果集合顺序 MUST 与 `workflow.runs` 的声明顺序一致
  r8,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r8,"dependent-nodes-start-after-prerequisites",workflow 中 node B 声明依赖 node A,workflow 在并发模式下调度执行,系统 MUST 在 node A 成功完成后才允许 node B 启动
  r8,"cycles-are-rejected-before-execution","workflow 中 A depends_on [B] 且 B depends_on [A]",workflow 被编译/校验,"系统 MUST fail-fast 并报告可读的 cycle 路径（例如 `[A, B, A]`）"
  r9,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r9,"ctx-is-only-readable-from-dependency-closure",node C 未声明依赖 node A,"node C 尝试读取 `{$ctx: {node: A, key: output_path}}`","系统 MUST fail-fast 并报告“ctx 引用超出 deps 可见范围”"
  r10,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r10,"downstream-can-consume-default-ctx-keys","node B depends_on [A]",node A 完成并发布默认 ctx summary,"node B MUST 能通过 `{$ctx: {node: A, key: total_rows}}` 读取该值并注入其输入"
  r11,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r11,"ctx-driven-init-vars-trigger-compile-on-ready","node B depends_on [A]",workflow 执行,系统 MUST 在 node A 完成并发布 ctx 后才物化编译 node B
  r12,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r12,"downstream-nodes-are-cancelled-on-upstream-failure","node B depends_on [A]",workflow 结束,"node B MUST 以 cancelled 结束,且原因应指向上游依赖失败"
  r13,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r13,"cache-pool-in-yaml-is-rejected-with-migration-guidance","",workflow YAML 包含 `workflow.options.cache_pool`,"系统 MUST fail-fast"
  r13,"share-preload-cache-is-rejected","",workflow YAML 包含 `workflow.options.share_preload_cache`,"系统 MUST fail-fast 报错（提示迁移到 runtime cache_pool preset） NOTE: cache pool 的语义(冲突策略/生命周期/预算/可观测性)由 `workflow-cache-pool` 能力规范定义."
  r14,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r14,"workflow-entrypoints-imports-in-a-minimal-py3-6-environment","仅安装了 `PyYAML` 与 `typing-extensions==4.1.1` 的 Python 3.6 环境","执行 `python -c \"from scalim.dsl.yaml_dsl import workflow_entrypoints\"`",import MUST 成功
  r14,"optional-dependencies-remain-optional-for-core-imports",环境中未安装 `openpyxl`,用户仅导入 Scalim 核心入口模块（包含 workflow 相关实现模块）,import MUST NOT 因 `openpyxl` 缺失而失败
  r15,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r15,"demand-events-can-be-joined-back-to-workflow-node-ids","workflow YAML 声明 runs: A/B",workflow 并发执行 A/B 两个 demand,"A 的 demand 事件 `Event.meta.workflow_node_id` MUST 等于 `\"A\"`"
  r15,"workflow-level-events-have-workflow-exec-id-run-partition","",workflow 调度开始/结束/取消某个节点,"对应的 workflow-level 事件 `Event.run_id` MUST 等于 `workflow_exec_id`"
  r16,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r16,"documentation-makes-component-concurrency-contract-explicit","",用户开启 `max_concurrency>1`,系统规范 MUST 明确 components 的线程安全/无状态要求
  r17,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r17,"workflow-yaml-rejects-removed-writes-field","workflow YAML 某个 run 包含 `writes: [...]`",workflow 被解析/校验/编译,"系统 MUST fail-fast 并指出“已移除的 workflow-level 写入 intents 字段”"
  r18,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r18,"resources-wait-in-yaml-is-rejected-with-an-actionable-migrat","",workflow YAML 声明 `workflow.options.resources_wait`,"系统 MUST fail-fast"
  r19,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r19,"output-staging-in-yaml-is-rejected-with-an-actionable-migrat","",workflow YAML 声明 `workflow.options.output_staging`,"系统 MUST fail-fast"
  r20,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r20,"scheduler-preset-is-configured-through-runtime-entrypoints-n",workflow YAML 仅声明 `workflow.runs` 与 `depends_on`,调用方以 `workflow_runtime_options.scheduler=stage_barrier` 运行 workflow,系统 MUST 以 stage_barrier 语义调度执行
  r21,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r21,"caller-can-import-scheduler-presets-from-yaml-dsl-facade","","调用方执行 `from scalim.dsl.yaml_dsl.workflow_types import PipelineSchedulerOptions, StageBarrierSchedulerOptions`",导入 MUST 成功
  r22,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r22,"workflow-execution-always-runs-preflight-before-engine-sched",workflow 存在某个可推理的 preflight 失败,用户调用 `run_workflow(...)`,系统 MUST 在 engine 启动前直接 raise
```
