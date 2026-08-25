# language: zh-CN
# capability: yaml-dsl-runtime-policy-boundary
# purpose: 将 runtime policy 从 YAML 主线迁出到 Python/CLI runtime entrypoints，并建立清晰的 policy boundary：parser-only 路径不运行 runtime-only diagnostics；c40 起 keys 分片与粗缓存/复用策略以 typed oneof 运行入口为 SSOT（YAML 覆盖优先级显式）。 [c40-yaml-runtime-policy-boundary] [c50-source-id-graph-refs]
# scope: src/scalim/

功能: yaml-dsl-runtime-policy-boundary

  @req:r126 @human
  场景: demand runtime-policy fields MUST move out of YAML mainline
    - demand 侧明显属于 runtime policy 的字段 MUST 从 YAML 主线迁出到 Python / CLI runtime entrypoints: - `guardrails.*` MUST 迁出 YAML - `retry.*` MUST 迁出 YAML - `batch_size` MUST 迁出 YAML(作为 runtime policy 不允许在 YAML 主线 authoring) - demand `failure_policy` MUST 迁出 YAML - `include_full_error_message` MUST 迁出 YAML - `validate_unique_field_names` MUST 迁出 YAML **Note:** 本要求约束的是 “runtime policy 的主线 authoring surface”。系统 MUST NOT 把 `batch_size` 等 runtime policy 重新引入 YAML authoring；若需要在运行时推导 derived 值,应通过 runtime entrypoints 的 typed surface（例如 hooks）实现,并保持调用方显式控制优先级最高。

  @req:r368 @human
  场景: environment-sensitive workflow runtime knobs MUST move out of YAML
    - workflow 中明显与环境、性能预算或发布策略绑定的 runtime knobs MUST 从 YAML 迁出（runtime policy boundary）： - `workflow.options` MUST NOT 再作为 workflow YAML 的 authoring surface（出现时 MUST fail-fast，并给出迁移指引）。 - 以下旧字段（含子字段）MUST 被视为 runtime policy 并从 YAML 迁出： - `workflow.options.max_concurrency` - `workflow.options.failure_policy` - `workflow.options.scheduler` - `workflow.options.cache_pool` - `workflow.options.resources_wait` - `workflow.options.output_staging` - `workflow.options.ctx` 作为“ctx size guardrails”配置入口 MUST 被移除；框架不再对 ctx payload 做 size-limit 报错（见 `yaml-dsl-workflow` 规范的 ctx 部分）。

  @req:r488 @human
  场景: workflow `failure_policy` MUST remain a stable orchestration knob
    - workflow `failure_policy` MUST 保持为稳定的 orchestration 语义并与 demand `failure_policy` 分离演进，但其配置 MUST 位于 runtime policy boundary（而不是 YAML authoring surface）： - workflow `failure_policy` MUST 继续参与 workflow 语义校验（在 effective runtime policy 边界） - 它 MUST 与 demand `failure_policy` 分离演进 - workflow YAML MUST NOT 再接受 `workflow.options.failure_policy` 作为 authoring 字段

  @req:r568 @human
  场景: extracted runtime policy MUST be controllable by runtime entrypoints and environ
    - 迁出后的 runtime policy MUST 由运行入口显式控制: - Python / CLI runtime entrypoints MUST 提供 typed surface - 对性能损耗显著的 guardrails,系统 MUST 支持按环境启停 - workflow compile 期间若为结构预加载 demand YAML，系统 MUST NOT 在尚未拿到 effective runtime policy 前抢跑 runtime-only diagnostics

  @req:r630 @human
  场景: workflow MUST run inferable runtime-only diagnostics at the effective-policy bou
    - 当 workflow 具备 per-run effective runtime policy（包括 run patches）以及 effective outputs/resources 口径后,系统 MUST 在进入 engine 调度前运行一组 inferable diagnostics（workflow preflight）。 该机制 MUST 满足: - diagnostics MUST NOT 在 workflow compile/preload 阶段抢跑 - diagnostics MUST 基于 effective policy/overrides 口径（避免 YAML 与 override 口径不一致导致误报/漏报）

  @req:r676 @human
  场景: demand parsing MUST be parser-only; runtime-only diagnostics MUST run only at po
    - 系统 MUST 将 demand 的“解析/结构化”与“runtime-only diagnostics/compile”彻底分离： - demand YAML 的 parse/loader API MUST 为 parser-only（只负责解析与结构抽取） - parser-only 路径 MUST NOT 运行任何依赖 effective runtime policy 的 diagnostics（例如 `validate_unique_field_names`） - runtime-only diagnostics MUST 仅在具备 effective runtime policy 的边界运行（例如 workflow preflight 或 demand runtime compile）

  @req:r716 @human
  场景: parser-only demand loader MUST NOT expose runtime-only diagnostics knobs
    - 为减少误用面并从结构上约束边界，系统提供的 parser-only demand loader MUST NOT 暴露任何“启用/禁用 runtime-only diagnostics”的参数（例如 `validate_unique_field_names` 这类开关）；runtime-only diagnostics 必须只能通过 policy-aware 边界的 typed runtime policy 输入控制。

  @req:r749 @human
  场景: derived runtime policy MUST NOT reduce caller control
    - 当系统通过 runtime hooks 推导 derived runtime policy（例如 derived `batch_size`）时,系统 MUST 保持调用方的显式 runtime policy 具有最高优先级: - 调用方显式提供 `RunOptions(batch_size=<int|None>)` 时,系统 MUST 使用显式值且 MUST 跳过 `pre_use_batch_size` policy signal。 - workflow per-run patch 显式提供 `batch_size=<int|None>` 时,系统 MUST 使用 patch 值且 MUST 跳过 `pre_use_batch_size` policy signal。

  @req:r776 @human
  场景: book write_defaults MUST use Python runtime policy; book budget MUST NOT be provided
    - 系统 MUST 将 book 级写入策略从 YAML authoring 迁出到 Python BookWritePolicy SSOT: - resources.books.*.write_defaults MUST NOT 再作为 YAML 主线 authoring 字段 - 当调用方未提供显式 write policy 时系统 MUST 使用 builtin defaults - YAML 中出现 write_defaults 时 MUST fail-fast 并提示改用 Python BookWritePolicy - 系统 MUST NOT 再提供 book cell/sheet 预算（BookBudgetPolicy 已移除）; YAML 残留 budget（含旧 xlsx_memory.budget）MUST fail-fast 并提示删除该字段（内存风险交宿主）

  @req:r155 @human
  场景: shared-book memory release knobs MUST stay off YAML authoring
    - 与共享 book 峰值内存相关的释放策略 MUST NOT 回流 YAML authoring: - MUST NOT 将 streaming/flush/budget/release knobs 引入 YAML（包括 outputs.write） - book cell/sheet 预算能力已移除（不得以 Python BookBudgetPolicy 形式重新引入，除非另开 change） - 本需求不引入 release 积极程度或 spill/seal 的 YAML/Python 新旋钮；该类能力若转正 MUST 另开 change 并保持非 YAML authoring - 任何后续 streaming-xlsx 类优化若转正，MUST 先 reframe 为 Python/profile 入口（见 notplan/futures）

  @req:r176 @human
  场景: ExcelColumnResidency CHUNKED MUST fail-fast with YAML output composition
    - 系统 MUST 将 `ExcelColumnResidency` 仅作为 Python runtime policy(例如 `DemandRunRuntimeOptions` / `ExecutionRequest`)暴露: - YAML authoring MUST NOT 声明 residency/streaming sink 实现字段 - 当请求同时携带 `output_composition`(YAML books/多输出行组合)与 `ExcelColumnResidency.CHUNKED` 时,系统 MUST fail-fast 并给出可诊断迁移提示 - MUST NOT 静默忽略 CHUNKED(避免假开关)

  @req:r1107 @human
  场景: OutputWriteLayout MUST stay Python-only; column layouts conflict with composition
    - 系统 MUST 将 `OutputWriteLayout`（若提供）仅作为 Python runtime policy 暴露（见 `runtime-output-write-layout`）: - YAML authoring MUST NOT 声明 `output_write_layout` 或等价 sink 布局字段 - 当存在 `output_composition` 且 effective layout 为 `column_buffered` 或 `column_chunked` 时,系统 MUST fail-fast - MUST NOT 静默把列布局降为行流式

  @req:r1003 @human
  场景: sources lookup_chunk_size MUST leave YAML; LookupChunking is Python typed SSOT
    - 系统 MUST 将 keys 模式分片大小与片间并行从 YAML authoring 收口到 Python typed oneof（推荐名 `LookupChunking`）: - demand YAML MUST NOT 再接受 `sources.*.lookup_chunk_size` 作为主线 authoring 字段 - YAML 出现该字段时 MUST fail-fast 并给出迁移到 `DemandRunRuntimeOptions.lookup_chunking`（或等价）的友好提示 - 运行入口 MUST 提供 per-source `LookupChunking`：至少 `off()`（不分片）与 `sized(size=..., parallel=...)`（`size>=1`；`parallel` 仅允许出现在 sized 形态） - 未配置某 source 时 effective 分片 MUST 等价于 `off` - 片间并行 MUST 仅由 `sized(..., parallel=True)`（或等价）表达，且仍须满足 `execution-refloader-chunk-parallelism`（含 `parallel_mode=adaptive`） - 系统 MUST NOT 新增 YAML 并行键 - 旧平铺 `parallelize_lookup_chunks` MUST 迁移到 sized 的 parallel 语义（兼容窗内 MAY 接受旧布尔并映射，但 MUST NOT 作为推荐 SSOT） - 本条与 demand 顶层已迁出的 `batch_size`（主行分批）正交

  @req:r1004 @human
  场景: SourceCache and RowsReuse MAY stay in YAML with explicit Python override priority
    - 系统 MUST 允许 YAML 继续声明 `sources.*.cache_mode`（`none`/`preload_forever`）与 params 内 `$rows.cache_mode`（`batch`/`none`），并 MUST 在 Python `DemandRunRuntimeOptions` 提供 per-source typed 覆盖（推荐名 `SourceCache` 与 `RowsReuse`，类型名 MUST 拆开以免混称）: - 覆盖优先级 MUST 为：显式 Python 覆盖 > YAML 声明 > builtin 默认（source cache 默认 `none`；rows reuse 默认 `batch`） - 系统 MUST NOT 静默忽略 YAML 声明 - `SourceCache` 与 `RowsReuse` MUST NOT 共用同一个平铺 `cache_mode` API 字段 - workflow `cache_pool` MUST 继续只决定跨 run 共享；是否 preload 仍由 effective `SourceCache`/YAML `cache_mode` 决定 - `RowsReuse` 的 effective `cache_mode` MUST 从 DemandIr.sources 目录解析并用于 LoadRef 分组/relation signature（见 ir-source-relations r694/r1110），MUST NOT 读字段图嵌套快照

  @req:r1005 @human
  场景: csv encoding and output header defaults MUST stay documented and factory-aligned
    - 系统 MUST 保持下列默认并在工厂与 YAML 省略口径对齐: - `resources.files.*.csv_file.encoding` 省略时 effective MUST 为 `utf-8`（`DEFAULT_OUTPUT_ENCODING`） - `resources.books.*.xlsx.allow_formulas` 省略时 effective MUST 为 `true`（pathless book 仍 MUST 拒绝该字段） - `outputs[*].write.include_header` 省略时 effective MUST 为 `true` - `outputs[*].write.header_fields_output_by` 省略时 effective MUST 为 `name` - `RunOverrides` 标准工厂（含 `csv_file` / `xlsx_file_single_sheet` 等）的 `header_fields_output_by` 参数默认 MUST 为 `name`（与 YAML 省略一致） - IO 覆盖面（encoding / allow_formulas / OutputWriteOverride）MUST 继续可用
  @req:r126 @human
  场景: demand-runtime-policy-fields-in-yaml-are-rejected-with-migra
    - 必须成立：假如 某个 demand YAML 仍声明 `include_full_error_message` 或 `validate_unique_field_names` 或顶层 `batch_size`；当 用户执行 validate 或运行入口解析；那么 系统 MUST 拒绝其作为主线 authoring 字段
    假如 某个 demand YAML 仍声明 `include_full_error_message` 或 `validate_unique_field_names` 或顶层 `batch_size`
    当 用户执行 validate 或运行入口解析
    那么 系统 MUST 拒绝其作为主线 authoring 字段

  @req:r126 @human
  场景: runtime-policy-declarations-remain-rejected-in-yaml
    - 必须成立：假如 某个 demand YAML 试图声明顶层 `batch_size` 或其它 runtime policy 字段；当 用户执行 validate 或运行入口解析；那么 系统 MUST 拒绝其作为主线 authoring 字段
    假如 某个 demand YAML 试图声明顶层 `batch_size` 或其它 runtime policy 字段
    当 用户执行 validate 或运行入口解析
    那么 系统 MUST 拒绝其作为主线 authoring 字段
  @req:r368 @human
  场景: workflow-runtime-policy-in-yaml-is-rejected-with-migration-g
    - 必须成立：假如 workflow YAML 声明 `workflow.options`（例如 `workflow.options.max_concurrency`）；当 用户执行 workflow validate 或运行入口解析；那么 系统 MUST fail-fast
    假如 workflow YAML 声明 `workflow.options`（例如 `workflow.options.max_concurrency`）
    当 用户执行 workflow validate 或运行入口解析
    那么 系统 MUST fail-fast

  @req:r368 @human
  场景: workflow-staging-wait-policy-is-configured-through-runtime-e
    - 必须成立：当 用户需要调整共享资源等待超时或 staging 保留策略；那么 系统 MUST 通过 Python / CLI runtime entrypoints（`workflow_runtime_options.resources_wait` / `workflow_runtime_options.output_staging`）表达这些策略
    当 用户需要调整共享资源等待超时或 staging 保留策略
    那么 系统 MUST 通过 Python / CLI runtime entrypoints（`workflow_runtime_options.resources_wait` / `workflow_runtime_options.output_staging`）表达这些策略
  @req:r488 @human
  场景: workflow-failure-policy-is-configured-through-runtime-entryp
    - 必须成立：假如 调用方在运行入口提供 `workflow_runtime_options.execution.failure_policy=primary_only`；当 用户执行 `run_workflow(...)`；那么 workflow MUST 继续执行后续 nodes（符合 `primary_only` 语义）
    假如 调用方在运行入口提供 `workflow_runtime_options.execution.failure_policy=primary_only`
    当 用户执行 `run_workflow(...)`
    那么 workflow MUST 继续执行后续 nodes（符合 `primary_only` 语义）
  @req:r568 @human
  场景: expensive-guardrails-are-enabled-only-in-selected-environmen
    - 必须成立：当 某个 guardrail 在开发环境需要开启而生产环境需要关闭；那么 用户 MUST 能通过 runtime entrypoint 或环境选择切换该行为
    当 某个 guardrail 在开发环境需要开启而生产环境需要关闭
    那么 用户 MUST 能通过 runtime entrypoint 或环境选择切换该行为

  @req:r568 @human
  场景: workflow-compile-does-not-preempt-demand-diagnostics-policy
    - 必须成立：假如 某个 workflow run 引用的 demand YAML 含有 intentional duplicate effective field display names；当 系统执行 workflow compile 阶段的结构预加载；那么 系统 MUST NOT 因 `validate_unique_field_names` 在该阶段直接失败
    假如 某个 workflow run 引用的 demand YAML 含有 intentional duplicate effective field display names
    当 系统执行 workflow compile 阶段的结构预加载
    那么 系统 MUST NOT 因 `validate_unique_field_names` 在该阶段直接失败
  @req:r630 @human
  场景: preload-stays-structural-but-preflight-may-reject-duplicates
    - 必须成立：假如 某个 workflow run 引用的 demand YAML 含有 duplicate effective field display names；当 系统执行 workflow compile/preload 阶段的结构预加载（例如 `compile_workflow_ir(...)`）；那么 系统 MUST NOT 因该诊断直接失败
    假如 某个 workflow run 引用的 demand YAML 含有 duplicate effective field display names
    当 系统执行 workflow compile/preload 阶段的结构预加载（例如 `compile_workflow_ir(...)`）
    那么 系统 MUST NOT 因该诊断直接失败
  @req:r676 @human
  场景: parser-only-demand-load-does-not-fail-on-duplicate-display-n
    - 必须成立：假如 某个 demand fields 存在 duplicate effective field display names；当 系统仅执行 parser-only 的解析/结构预加载；那么 解析/预加载 MUST 成功返回结构信息
    假如 某个 demand fields 存在 duplicate effective field display names
    当 系统仅执行 parser-only 的解析/结构预加载
    那么 解析/预加载 MUST 成功返回结构信息
  @req:r716 @human
  场景: parser-only-loader-cannot-be-called-with-validate-unique-fie
    - 必须成立：当 调用方尝试以 `validate_unique_field_names=...` 调用 parser-only demand loader；那么 该调用 MUST 不可用（例如参数不存在或直接报错）
    当 调用方尝试以 `validate_unique_field_names=...` 调用 parser-only demand loader
    那么 该调用 MUST 不可用（例如参数不存在或直接报错）
  @req:r749 @human
  场景: explicit-batch-size-wins-over-policy-signal
    - 必须成立：当 调用方显式传入 `RunOptions(batch_size=8000)`；那么 effective `batch_size` MUST 为 `8000`
    当 调用方显式传入 `RunOptions(batch_size=8000)`
    那么 effective `batch_size` MUST 为 `8000`

  @req:r776 @human
  场景: yaml-rejects-write-defaults
    - 必须成立：假如 某个 workflow 或 demand YAML 在 resources.books.<id> 下声明 write_defaults；当 用户执行 validate 或运行入口解析；那么 系统 MUST fail-fast 并提示改用 Python BookWritePolicy（或等价 typed policy）
    假如 某个 workflow 或 demand YAML 在 resources.books.<id> 下声明 write_defaults
    当 用户执行 validate 或运行入口解析
    那么 系统 MUST fail-fast 并提示改用 Python BookWritePolicy（或等价 typed policy）

  @req:r776 @human
  场景: builtin-defaults-without-policy
    - 必须成立：假如 YAML 仅声明 books id/variant/path 且调用方未传 book write policy；当 用户执行 run_workflow 或等价入口；那么 系统 MUST 使用 builtin write defaults（等价 mode=sheet 与历史 on_conflict/align_by/header_policy/on_mismatch 缺省）
    假如 YAML 仅声明 books id/variant/path 且调用方未传 book write policy
    当 用户执行 run_workflow 或等价入口
    那么 系统 MUST 使用 builtin write defaults（等价 mode=sheet 与历史 on_conflict/align_by/header_policy/on_mismatch 缺省）

  @req:r776 @human
  场景: yaml-rejects-residual-budget
    - 必须成立：假如 某个 workflow 或 demand YAML 在 resources.books 下声明 budget；当 用户执行 validate 或运行入口解析；那么 系统 MUST fail-fast 并提示删除该字段（不得再指向 BookBudgetPolicy）
    假如 某个 workflow 或 demand YAML 在 resources.books 下声明 budget
    当 用户执行 validate 或运行入口解析
    那么 系统 MUST fail-fast 并提示删除该字段（不得再指向 BookBudgetPolicy）

  @req:r155 @human
  场景: reject-yaml-streaming-knobs
    - 必须成立：假如 提案或配置试图在 outputs.write 下增加 streaming/flush 字段；当 按主线原则评审或 validate；那么 该方向 MUST 被视为偏离 runtime policy boundary（YAML 不得承载）
    假如 提案或配置试图在 outputs.write 下增加 streaming/flush 字段
    当 按主线原则评审或 validate
    那么 该方向 MUST 被视为偏离 runtime policy boundary（YAML 不得承载）

  @req:r176 @human
  场景: chunked-with-composition-fails-fast
    - 必须成立：假如 DemandRun/ExecutionRequest 设置 CHUNKED 且存在 output_composition；当 进入 run_ir 装配输出；那么 系统 MUST fail-fast 并提示 CHUNKED 仅适用于列式 IR 文件 sink
    假如 DemandRun/ExecutionRequest 设置 CHUNKED 且存在 output_composition
    当 进入 run_ir 装配输出
    那么 系统 MUST fail-fast 并提示 CHUNKED 仅适用于列式 IR 文件 sink

  @req:r176 @human
  场景: yaml-must-not-author-residency
    - 必须成立：假如 某 demand YAML 试图声明 excel_column_residency 或 write.streaming；当 validate 或 parse；那么 系统 MUST 拒绝作为主线 authoring 字段
    假如 某 demand YAML 试图声明 excel_column_residency 或 write.streaming
    当 validate 或 parse
    那么 系统 MUST 拒绝作为主线 authoring 字段

  @req:r1107 @human
  场景: yaml-must-not-author-output-write-layout
    - 必须成立：假如 某 demand YAML 试图声明 output_write_layout 或等价 sink 布局字段；当 validate 或 parse；那么 系统 MUST fail-fast
    假如 某 demand YAML 试图声明 output_write_layout 或等价 sink 布局字段
    当 validate 或 parse
    那么 系统 MUST fail-fast

  @req:r1107 @human
  场景: composition-plus-column-layout-fails-fast
    - 必须成立：假如 DemandRun/ExecutionRequest effective layout 为 column_buffered 或 column_chunked 且存在 output_composition；当 进入 run_ir 装配输出；那么 系统 MUST fail-fast
    假如 DemandRun/ExecutionRequest effective layout 为 column_buffered 或 column_chunked 且存在 output_composition
    当 进入 run_ir 装配输出
    那么 系统 MUST fail-fast

  @req:r1003 @human
  场景: yaml-rejects-lookup-chunk-size
    - 必须成立：假如 某个 demand YAML 在 sources.<id> 下声明 lookup_chunk_size；当 用户执行 validate 或运行入口解析；那么 系统 MUST fail-fast 并提示改用 DemandRunRuntimeOptions.lookup_chunking / LookupChunking
    假如 某个 demand YAML 在 sources.<id> 下声明 lookup_chunk_size
    当 用户执行 validate 或运行入口解析
    那么 系统 MUST fail-fast 并提示改用 DemandRunRuntimeOptions.lookup_chunking / LookupChunking

  @req:r1003 @human
  场景: lookup-chunking-sized-parallel-nested
    - 必须成立：假如 调用方对 source customers 设置 LookupChunking.sized(size=10 parallel=True) 且 parallel_mode=adaptive；当 执行 keys LoadRef 且 lookup_keys 足够多；那么 系统 MUST 按 size 分片且允许片间并行（受 chunk-parallelism 护栏约束）
    假如 调用方对 source customers 设置 LookupChunking.sized(size=10 parallel=True) 且 parallel_mode=adaptive
    当 执行 keys LoadRef 且 lookup_keys 足够多
    那么 系统 MUST 按 size 分片且允许片间并行（受 chunk-parallelism 护栏约束）

  @req:r1003 @human
  场景: lookup-chunking-off-is-default
    - 必须成立：假如 调用方未配置 lookup_chunking 且 YAML 无 lookup_chunk_size；当 执行 keys LoadRef；那么 系统 MUST 单次 loader 调用（不分片）
    假如 调用方未配置 lookup_chunking 且 YAML 无 lookup_chunk_size
    当 执行 keys LoadRef
    那么 系统 MUST 单次 loader 调用（不分片）

  @req:r1004 @human
  场景: python-source-cache-overrides-yaml
    - 必须成立：假如 YAML 声明 sources.dim.cache_mode=none 且 runtime 提供 source_cache dim=SourceCache.preload_forever()；当 compile/run；那么 effective cache 策略 MUST 为 preload_forever
    假如 YAML 声明 sources.dim.cache_mode=none 且 runtime 提供 source_cache dim=SourceCache.preload_forever()
    当 compile/run
    那么 effective cache 策略 MUST 为 preload_forever

  @req:r1004 @human
  场景: python-rows-reuse-overrides-yaml
    - 必须成立：假如 YAML params 使用 $rows.cache_mode=batch 且 runtime 提供 rows_reuse=RowsReuse.none()；当 执行该 source 的 rows 绑定 LoadRef；那么 系统 MUST 按 none 禁用批次内 relation 复用
    假如 YAML params 使用 $rows.cache_mode=batch 且 runtime 提供 rows_reuse=RowsReuse.none()
    当 执行该 source 的 rows 绑定 LoadRef
    那么 系统 MUST 按 none 禁用批次内 relation 复用

  @req:r1005 @human
  场景: csv-encoding-defaults-to-utf8
    - 必须成立：假如 resources.files 声明 csv_file 且省略 encoding；当 物化/写出 CSV；那么 effective encoding MUST 为 utf-8
    假如 resources.files 声明 csv_file 且省略 encoding
    当 物化/写出 CSV
    那么 effective encoding MUST 为 utf-8

  @req:r1005 @human
  场景: runoverrides-factory-header-default-is-name
    - 必须成立：当 调用 RunOverrides.csv_file 或 xlsx_file_single_sheet 且不传 header_fields_output_by；那么 构造结果中 header_fields_output_by MUST 默认为 name
    当 调用 RunOverrides.csv_file 或 xlsx_file_single_sheet 且不传 header_fields_output_by
    那么 构造结果中 header_fields_output_by MUST 默认为 name
