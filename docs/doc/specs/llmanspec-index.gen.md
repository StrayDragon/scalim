<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `llmanspec/specs/*/*.feature`
-->

??? warning "自动生成文件"
    本文件由 `scripts/gen-docs.py` 自动生成，请勿手动编辑。如需修改，请编辑源文件或生成脚本。

# llmanspec 索引(生成)

说明:
- 本页仅做“索引与链接”,不把 `llmanspec/specs/**` 作为站点页面.
- 规范本体以仓库文件为准,请通过代码链接打开.

## Specs

### `cli-yaml-dsl-viz-compile`
- Title: cli-yaml-dsl-viz-compile
- Source: [cli-yaml-dsl-viz-compile.feature](repo:llmanspec/specs/cli-yaml-dsl-viz-compile/cli-yaml-dsl-viz-compile.feature)
- Summary: TBD - created by archiving change c0-yaml-dsl-viz-compile-cli. Update Purpose after archive. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `demand-dsl`
- Title: demand-dsl
- Source: [demand-dsl.feature](repo:llmanspec/specs/demand-dsl/demand-dsl.feature)
- Summary: 实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `dsl-runtime-structure`
- Title: dsl-runtime-structure
- Source: [dsl-runtime-structure.feature](repo:llmanspec/specs/dsl-runtime-structure/dsl-runtime-structure.feature)
- Summary: 定义 YAML DSL runtime 作为 DSL adapter/编译器的边界与对外入口，明确 YAML 配置（outputs/可观测性/retry 等）在编译期映射为 DSL-agnostic 运行请求对象的规则。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `examples-marimo`
- Title: examples-marimo
- Source: [examples-marimo.feature](repo:llmanspec/specs/examples-marimo/examples-marimo.feature)
- Summary: 定义仓库内 Marimo 示例/教学套件治理边界：Marimo notebooks 作为唯一交互载体，headless runner/pytest 作为确定性回归入口，要求执行真相来源位于 notebooks（同源复用）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-adaptive-guardrails`
- Title: execution-adaptive-guardrails
- Source: [execution-adaptive-guardrails.feature](repo:llmanspec/specs/execution-adaptive-guardrails/execution-adaptive-guardrails.feature)
- Summary: 定义 adaptive execution 的硬护栏：显式 `max_workers` 的 hard cap 与可选的任务等待超时（fail-fast 诊断）；chunk 并行复用本护栏的 W/`task_timeout_s`（见 `execution-refloader-chunk-parallelism`）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-call-by-memoization`
- Title: execution-call-by-memoization
- Source: [execution-call-by-memoization.feature](repo:llmanspec/specs/execution-call-by-memoization/execution-call-by-memoization.feature)
- Summary: 为 `ctx-free call_by` 派生字段提供实验性 LRU 记忆化：字段级 allow/deny 过滤、硬上限 LRU、与可选性能统计日志（默认关闭）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-compute-rowwise-fusion`
- Title: execution-compute-rowwise-fusion
- Source: [execution-compute-rowwise-fusion.feature](repo:llmanspec/specs/execution-compute-rowwise-fusion/execution-compute-rowwise-fusion.feature)
- Summary: 在 compute 段对满足约束的派生字段做 row-wise / 同依赖复用融合，降低 N×M 框架税；保持值语义与每字段每行计算器调用次数；安全外壳外回退 field-major。 [c20-compute-expr-rowwise-fusion]

### `execution-concurrency-safety`
- Title: execution-concurrency-safety
- Source: [execution-concurrency-safety.feature](repo:llmanspec/specs/execution-concurrency-safety/execution-concurrency-safety.feature)
- Summary: 为执行层的并发安全定义护栏：任何可能触发用户回调（hooks/observers）或外部回调的操作不得在内部互斥锁临界区内执行，避免重入/锁顺序反转导致的死锁。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-dense-batch`
- Title: execution-dense-batch
- Source: [execution-dense-batch.feature](repo:llmanspec/specs/execution-dense-batch/execution-dense-batch.feature)
- Summary: 优化批次执行场景的内存占用与访问速度，通过 Dense 存储表示支持连续整数 row_id 的紧凑编码。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-derived-outputs`
- Title: execution-derived-outputs
- Source: [execution-derived-outputs.feature](repo:llmanspec/specs/execution-derived-outputs/execution-derived-outputs.feature)
- Summary: 支持在同一次运行中基于详情行流生成派生输出(增量聚合 + finalize 阶段输出),并定义 IR/Python-only 配置入口、资源护栏与 `adaptive` 并发边界. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-error-taxonomy`
- Title: execution-error-taxonomy
- Source: [execution-error-taxonomy.feature](repo:llmanspec/specs/execution-error-taxonomy/execution-error-taxonomy.feature)
- Summary: 为 scalim 建立统一的异常体系规范:以 ScalimError 作为唯一根,并在其下按域拆分子类;对用户可感知错误以异常类型/显式字段作为稳定契约;同时约束错误事件的最小输出与敏感信息治理,并提供可执行的测试断言口径. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-hotpath-fastpaths`
- Title: execution-hotpath-fastpaths
- Source: [execution-hotpath-fastpaths.feature](repo:llmanspec/specs/execution-hotpath-fastpaths/execution-hotpath-fastpaths.feature)
- Summary: 在不要求业务改动的前提下，降低 execution 热路径（`compute` / `call_by` / `load_ref` / write-precompute / row-wise fusion）的 per-row 固定开销与中间驻留，并保持既有值语义、可观测性与低内存特性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence] [c10-write-precompute-derived-fields] [c20-compute-expr-rowwise-fusion]

### `execution-loader-retry`
- Title: execution-loader-retry
- Source: [execution-loader-retry.feature](repo:llmanspec/specs/execution-loader-retry/execution-loader-retry.feature)
- Summary: 提供可配置的 loader retry policy 机制，在 loader 调用因瞬态错误失败时执行有限的自动重试，支持全局默认策略与 per-source 覆盖，并通过可配置的退避策略、次数上限和耗时上限防止无限重试。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-micro-tunes`
- Title: execution-micro-tunes
- Source: [execution-micro-tunes.feature](repo:llmanspec/specs/execution-micro-tunes/execution-micro-tunes.feature)
- Summary: 定义 YAML DSL 语法增强，简化常见场景的表达复杂度，包括 relation 引用语法糖、output.fields 简写、runtime vars 指令节点形式，以及改进的验证器诊断信息。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-output-composition`
- Title: execution-output-composition
- Source: [execution-output-composition.feature](repo:llmanspec/specs/execution-output-composition/execution-output-composition.feature)
- Summary: 支持单次运行的多输出目标组合(多文件或同一容器多逻辑输出),并定义容器命名冲突策略与输出失败策略(`failure_policy`). [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-preload-cache`
- Title: execution-preload-cache
- Source: [execution-preload-cache.feature](repo:llmanspec/specs/execution-preload-cache/execution-preload-cache.feature)
- Summary: 定义 `PreloadCache` 的完整行为契约：并发安全性、in-flight 去重、signature 冲突防护、诊断能力，以及并发场景下的幂等性期望。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-ref-miss-default-cases`
- Title: execution-ref-miss-default-cases
- Source: [execution-ref-miss-default-cases.feature](repo:llmanspec/specs/execution-ref-miss-default-cases/execution-ref-miss-default-cases.feature)
- Summary: 定义 YAML DSL 中 source ref 字段的 relation miss 默认值机制。允许用户在关联查询未命中时使用有序的默认值替代 None，提高配置表达能力和错误容错性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-refloader-chunk-parallelism`
- Title: execution-refloader-chunk-parallelism
- Source: [execution-refloader-chunk-parallelism.feature](repo:llmanspec/specs/execution-refloader-chunk-parallelism/execution-refloader-chunk-parallelism.feature)
- Summary: 在 keys 模式由 Python `LookupChunking.sized` 产生的分片路径上提供 nested parallel opt-in；默认串行；合并语义与 `ir-source-relations` r694 串行分片一致。分片大小 SSOT 见 `yaml-dsl-runtime-policy-boundary` r1003（不再用 YAML `lookup_chunk_size`）。 [c30-refloader-chunk-parallelism][c40-yaml-runtime-policy-boundary]

### `execution-safety-single-writer`
- Title: execution-safety-single-writer
- Source: [execution-safety-single-writer.feature](repo:llmanspec/specs/execution-safety-single-writer/execution-safety-single-writer.feature)
- Summary: Establish and enforce a single-writer threading model for workflow execution state, ensuring that write operations to shared runtime structures are either owned by a controller thread or protected by [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `execution-structure`
- Title: execution-structure
- Source: [execution-structure.feature](repo:llmanspec/specs/execution-structure/execution-structure.feature)
- Summary: 定义 execution 层的模块拆分与入口契约,并明确统一 IR 编排入口(如 `run_ir`)的边界,确保执行编排对 DSL 配置解耦且行为在重构后保持兼容. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-docs`
- Title: governance-docs
- Source: [governance-docs.feature](repo:llmanspec/specs/governance-docs/governance-docs.feature)
- Summary: 定义仓库内文档的分层、生成边界(`*.gen.*` + `AUTOGEN` 注入区块)、统一生成入口与漂移门禁,以降低维护成本并防止”手工修改生成物/区块”导致的不一致. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-docs-site`
- Title: governance-docs-site
- Source: [governance-docs-site.feature](repo:llmanspec/specs/governance-docs-site/governance-docs-site.feature)
- Summary: 定义仓库内文档站点的范围与组织规则：使用 Zensical（兼容 MkDocs 的配置格式）构建站点，以 `docs/doc/` 作为唯一文档真源，避免将规范、审计报告等纳入站点。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-extension-points`
- Title: governance-extension-points
- Source: [governance-extension-points.feature](repo:llmanspec/specs/governance-extension-points/governance-extension-points.feature)
- Summary: 定义 PROJECT_NAME 内部扩展点的显式注入与编译式分发模型，减少模块级”魔法注入”与事件热路径反射，提升类型友好性、可维护性与性能稳定性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-mainline-principles`
- Title: governance-mainline-principles
- Source: [governance-mainline-principles.feature](repo:llmanspec/specs/governance-mainline-principles/governance-mainline-principles.feature)
- Summary: 定义 YAML DSL 的上位主线原则与设计护栏，用于约束后续变更的方向与评审口径：单主线原地演进、authoring/runtime policy 分离、KV-first、以及 workflow 小而声明式（拒绝 imports expansion）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-misc`
- Title: governance-misc
- Source: [governance-misc.feature](repo:llmanspec/specs/governance-misc/governance-misc.feature)
- Summary: 为“重构分析类文档”提供统一的规范入口与最低要求,确保依赖分析、边界说明、任务拆分、验证口径和约束声明一致,以便在不改动代码的前提下形成可复核的决策依据. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-module-organization`
- Title: governance-module-organization
- Source: [governance-module-organization.feature](repo:llmanspec/specs/governance-module-organization/governance-module-organization.feature)
- Summary: 定义运行时模块的边界、入口最小化与依赖约束,避免将内部实现路径误用为公共 API,并保持模块层级单向依赖与 Python 3.6 运行时兼容性. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-package-identity`
- Title: governance-package-identity
- Source: [governance-package-identity.feature](repo:llmanspec/specs/governance-package-identity/governance-package-identity.feature)
- Summary: 定义项目包身份与分发边界的治理规范，确保 PyPI 发行名、导入根包名、CLI 命令名之间的清晰分离，以及运行时主包与 CLI 发行物的版本约束解耦。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-public-api`
- Title: governance-public-api
- Source: [governance-public-api.feature](repo:llmanspec/specs/governance-public-api/governance-public-api.feature)
- Summary: 定义 public API 边界治理规则：稳定入口编目、`__all__` 治理、用户材料导入边界、agent skill 生成器，确保在不引入"符号级硬 manifest SSOT"的前提下维护清晰的公共契约。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `governance-readme-examples`
- Title: governance-readme-examples
- Source: [governance-readme-examples.feature](repo:llmanspec/specs/governance-readme-examples/governance-readme-examples.feature)
- Summary: 定义根 README 受控示例的公开页注入、图表资产与漂移校验；可执行 SSOT 位于 marimo README suite（见 examples-marimo），保证公开页与仓库真相一致（含本地 RSS 增量代理与版本锚定性能证据）。

### `hooks-events`
- Title: hooks-events
- Source: [hooks-events.feature](repo:llmanspec/specs/hooks-events/hooks-events.feature)
- Summary: 定义 hooks 和事件系统的事件类型和策略决策信号规范,包括 loader retry 事件和 policy decision signals。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `hooks-observability-structure`
- Title: hooks-observability-structure
- Source: [hooks-observability-structure.feature](repo:llmanspec/specs/hooks-observability-structure/hooks-observability-structure.feature)
- Summary: 定义 Hook/Observer/事件体系的统一边界:事件契约、分发路径、组件装配与高频路径性能语义. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `ir-field-compute`
- Title: ir-field-compute
- Source: [ir-field-compute.feature](repo:llmanspec/specs/ir-field-compute/ir-field-compute.feature)
- Summary: 定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `ir-key-normalization`
- Title: ir-key-normalization
- Source: [ir-key-normalization.feature](repo:llmanspec/specs/ir-key-normalization/ir-key-normalization.feature)
- Summary: `key_normalization` 提供一个运行期可控的”稳定字符串口径”键匹配策略,用于解决 relations/derived outputs 中跨来源类型不一致导致的 miss/分组拆分问题(例如 `1` 与 `”1”`). 该能力为 `EXPERIMENTAL`,默认关闭(`raw`). [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `ir-source-relations`
- Title: ir-source-relations
- Source: [ir-source-relations.feature](repo:llmanspec/specs/ir-source-relations/ir-source-relations.feature)
- Summary: 使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义. [scope-review-2026-07-13-c25-xlsx-ir-path-presence] [c50-source-id-graph-refs]

### `ir-structure`
- Title: ir-structure
- Source: [ir-structure.feature](repo:llmanspec/specs/ir-structure/ir-structure.feature)
- Summary: 定义 IR 层的纯数据边界与依赖约束,确保 spec/ir 不依赖执行与规划层,便于稳定复用、演进与测试. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `observability-flow-visualization`
- Title: observability-flow-visualization
- Source: [observability-flow-visualization.feature](repo:llmanspec/specs/observability-flow-visualization/observability-flow-visualization.feature)
- Summary: 提供执行过程的可视化输出:VizGraphSnapshot 从 ExecutionPlan 生成 XYFlow 兼容的 nodes/edges 结构用于依赖图展示;VizEventStream 将 Hook 事件映射为可视化事件流支持离线回放. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `observability-logging`
- Title: observability-logging
- Source: [observability-logging.feature](repo:llmanspec/specs/observability-logging/observability-logging.feature)
- Summary: 为框架内部日志建立统一的 Python 标准库 `logging` 使用约定,以保证默认静默、命名空间稳定、输出前缀一致,并提供可扩展的诊断字段与 context 绑定机制。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `observability-observer-concurrency`
- Title: observability-observer-concurrency
- Source: [observability-observer-concurrency.feature](repo:llmanspec/specs/observability-observer-concurrency/observability-observer-concurrency.feature)
- Summary: 定义 workflow 并发执行时 observers/hooks/components 的默认并发语义,确保在不要求 observer 实现方线程安全的前提下仍具备可解释、可复现的事件回放顺序,并保持 `no-external-callback-under-lock` 护栏不被破坏. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `observability-run-stats`
- Title: observability-run-stats
- Source: [observability-run-stats.feature](repo:llmanspec/specs/observability-run-stats/observability-run-stats.feature)
- Summary: 低漂移自我观测底座：版本化 run_stats、workflow nodes[] 快照、bench/debug profiles、高影响观测警告，以及可选 viz sibling 产物。

### `output-mode-api`
- Title: output-mode-api
- Source: [output-mode-api.feature](repo:llmanspec/specs/output-mode-api/output-mode-api.feature)
- Summary: 定义运行时输出语义为"显式 sink 驱动": 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `output-sink-contracts`
- Title: output-sink-contracts
- Source: [output-sink-contracts.feature](repo:llmanspec/specs/output-sink-contracts/output-sink-contracts.feature)
- Summary: 定义 sink 接口稳定性与可选依赖提示规范，确保内建与外部 sink 的长期兼容、可诊断性与一致行为。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `output-sink-fastpath`
- Title: output-sink-fastpath
- Source: [output-sink-fastpath.feature](repo:llmanspec/specs/output-sink-fastpath/output-sink-fastpath.feature)
- Summary: 为 sinks 提供可选的 aligned-write fastpath 接口（`write_column_aligned`/`write_row_aligned`），pipeline 优先使用 fastpath 以避免中间 dict 分配，回退兼容现有接口。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `parallel-execution`
- Title: parallel-execution
- Source: [parallel-execution.feature](repo:llmanspec/specs/parallel-execution/parallel-execution.feature)
- Summary: 定义执行层对外并发语义 `seq|adaptive`,以及 `adaptive` 下的调度边界、后端选择、结果提交与事件回放契约;并交叉引用同 LoadRef 内 chunk 并行层次（见 `execution-refloader-chunk-parallelism`）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `performance-observability`
- Title: performance-observability
- Source: [performance-observability.feature](repo:llmanspec/specs/performance-observability/performance-observability.feature)
- Summary: PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `planning-deterministic-ordering`
- Title: planning-deterministic-ordering
- Source: [planning-deterministic-ordering.feature](repo:llmanspec/specs/planning-deterministic-ordering/planning-deterministic-ordering.feature)
- Summary: 定义 PROJECT_NAME 的稳定顺序最小契约，用于保证 planning/执行在相同输入下可复现，并避免 `PYTHONHASHSEED` 等非确定性因素影响结果。 本 spec 覆盖执行计划构建顺序、拓扑排序输出的 tie-break 规则、以及 keys 绑定列表的稳定顺序要求。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `quality-benchmarking`
- Title: quality-benchmarking
- Source: [quality-benchmarking.feature](repo:llmanspec/specs/quality-benchmarking/quality-benchmarking.feature)
- Summary: 定义基准测试入口与依赖约束，覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `runtime-guardrails`
- Title: runtime-guardrails
- Source: [runtime-guardrails.feature](repo:llmanspec/specs/runtime-guardrails/runtime-guardrails.feature)
- Summary: 定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `runtime-output-write-layout`
- Title: runtime-output-write-layout
- Source: [runtime-output-write-layout.feature](repo:llmanspec/specs/runtime-output-write-layout/runtime-output-write-layout.feature)
- Summary: 闭集 OutputWriteLayout（row_stream/column_buffered/column_chunked）作为 Python SSOT，统一文件 sink 工厂选择与互斥 fail-fast；禁止 YAML authoring 与静默自动切换。

### `runtime-policy-normalization`
- Title: runtime-policy-normalization
- Source: [runtime-policy-normalization.feature](repo:llmanspec/specs/runtime-policy-normalization/runtime-policy-normalization.feature)
- Summary: 定义运行期 policy 值的归一化契约：以 Enum 为封闭集合的 SSOT，state/serialization 边界编/解码为 builtin `str`，允许值集合从 Enum 单一派生。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `runtime-pruning`
- Title: runtime-pruning
- Source: [runtime-pruning.feature](repo:llmanspec/specs/runtime-pruning/runtime-pruning.feature)
- Summary: PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `runtime-typedef-aliases`
- Title: runtime-typedef-aliases
- Source: [runtime-typedef-aliases.feature](repo:llmanspec/specs/runtime-typedef-aliases/runtime-typedef-aliases.feature)
- Summary: 收敛公开记录键类型别名：BusinessKey 为 SSOT，移除 RowId/RowIdSeq/RowIdList 兼容别名。

### `streaming-output`
- Title: streaming-output
- Source: [streaming-output.feature](repo:llmanspec/specs/streaming-output/streaming-output.feature)
- Summary: 支持 IRowSink 与 IColumnSink 的流式写入路径,定义 main source 行流、分批与 `row_id` 规则,并约束行式路径"行就绪即写出 + rows 绑定 release 屏障"语义. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `structured-logging`
- Title: structured-logging
- Source: [structured-logging.feature](repo:llmanspec/specs/structured-logging/structured-logging.feature)
- Summary: 定义结构化日志的 JSONL 输出格式、字段元信息、归因上下文自动注入及 CLI 渲染能力，确保日志可被机器解析与人类友好展示。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `testing-quality`
- Title: testing-quality
- Source: [testing-quality.feature](repo:llmanspec/specs/testing-quality/testing-quality.feature)
- Summary: 定义测试分类、覆盖率门槛与 demo 对拍验证的最低要求,明确默认测试范围与质量门禁,确保持续集成结果稳定可复现. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `tests-domain-suites`
- Title: tests-domain-suites
- Source: [tests-domain-suites.feature](repo:llmanspec/specs/tests-domain-suites/tests-domain-suites.feature)
- Summary: 将测试按领域组织为显式套件目录，约束 YAML string-reference fixtures 放在 tests/fixtures/，禁止 additional 模式，并确保 governance 聚焦于契约测试和脚本单元测试。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `tools-agent-skill-export`
- Title: tools-agent-skill-export
- Source: [tools-agent-skill-export.feature](repo:llmanspec/specs/tools-agent-skill-export/tools-agent-skill-export.feature)
- Summary: 定义 `scalim-yaml-dsl` skill 自动生成器的职责边界，确保自动化只负责受控参考产物，同时保证输出可校验、可重建、不会覆盖手工维护的 skill 本体。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `tools-console-reports`
- Title: tools-console-reports
- Source: [tools-console-reports.feature](repo:llmanspec/specs/tools-console-reports/tools-console-reports.feature)
- Summary: 定义 console 报告输出契约：仅依赖标准库 `logging` 的逐行 `k=v` 文本输出，无表格/边框依赖，per-entity 明细以重复行表达，样本有界。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `tools-prompt-eval-cli`
- Title: tools-prompt-eval-cli
- Source: [tools-prompt-eval-cli.feature](repo:llmanspec/specs/tools-prompt-eval-cli/tools-prompt-eval-cli.feature)
- Summary: 定义 prompt-eval coding-agent workspace 的 fixture CLI 隔离策略，确保其不覆盖仓库真实 `scalim-cli`，同时保持 workspace 内 `uv run scalim-cli ...` 命令模板可复现，并避免对 PyPI build 依赖/网络造成的 dry-run 波动。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `tools-prompt-eval-workflow`
- Title: tools-prompt-eval-workflow
- Source: [tools-prompt-eval-workflow.feature](repo:llmanspec/specs/tools-prompt-eval-workflow/tools-prompt-eval-workflow.feature)
- Summary: 定义仓库级 prompt 评测/回归工作流的最低要求,用于守护关键 skill/指令文本的质量与文档治理边界规则,并提供稳定的本地运行入口与 CI 产物。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `tools-resources-discovery`
- Title: tools-resources-discovery
- Source: [tools-resources-discovery.feature](repo:llmanspec/specs/tools-resources-discovery/tools-resources-discovery.feature)
- Summary: 定义面向用户的稳定公开入口,用于从 output root 定位“最新一次成功发布”的产物集合(books/files),并隐藏底层 D-2 版本化输出协议的内部落盘细节. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `vendor-dataclassesx`
- Title: vendor-dataclassesx
- Source: [vendor-dataclassesx.feature](repo:llmanspec/specs/vendor-dataclassesx/vendor-dataclassesx.feature)
- Summary: 为 `scalim/` 提供一个可 vendors 化、可审计的 dataclasses 能力入口,在保持 Python 3.6 运行时兼容的同时避免依赖外部 `dataclasses` backport,并避免包内绝对导入在多份包共存时混入错误实现。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `vendor-legacy-sync`
- Title: vendor-legacy-sync
- Source: [vendor-legacy-sync.feature](repo:llmanspec/specs/vendor-legacy-sync/vendor-legacy-sync.feature)
- Summary: 为下游采用 `vendors/libs/` 导入链路的旧工程提供一个可审计、可重复的同步入口,用于将本仓库的 `src/scalim/` vendors 化后镜像到目标 `<vendors/libs>/scalim/`。默认仅预览(dry-run),并在显式确认时执行实际同步。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-cache-pool`
- Title: workflow-cache-pool
- Source: [workflow-cache-pool.feature](repo:llmanspec/specs/workflow-cache-pool/workflow-cache-pool.feature)
- Summary: 提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件/并发安全确保"复用正确且可诊断". [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-execute-organization`
- Title: workflow-execute-organization
- Source: [workflow-execute-organization.feature](repo:llmanspec/specs/workflow-execute-organization/workflow-execute-organization.feature)
- Summary: 重构 workflow execute 模块结构（extract outcome_builder/scheduler_rules/resource_lifecycle/viz_reporter），不改变外部可观测行为、不增加热路径开销，并保持 Python 3.6 兼容。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-intermediate-store`
- Title: workflow-intermediate-store
- Source: [workflow-intermediate-store.feature](repo:llmanspec/specs/workflow-intermediate-store/workflow-intermediate-store.feature)
- Summary: 定义 workflow 中间存储 `InMemoryRows` 作为节点间纯 Python 表格数据传递的基础设施：表结构契约、workflow YAML `main_rows_from` 显式接线、`InMemoryCsv` 转换、生命周期管理与稳定公开导入路径。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-ir`
- Title: workflow-ir
- Source: [workflow-ir.feature](repo:llmanspec/specs/workflow-ir/workflow-ir.feature)
- Summary: 定义 Workflow IR 作为 workflow 的统一底座,并将 workflow 的 authoring surface(例如 YAML)视为"编译到 IR 的语法前端",而不是直接驱动执行器分支逻辑. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-managed-temp-outputs`
- Title: workflow-managed-temp-outputs
- Source: [workflow-managed-temp-outputs.feature](repo:llmanspec/specs/workflow-managed-temp-outputs/workflow-managed-temp-outputs.feature)
- Summary: 允许 workflow 托管仅供写入节点消费的中间态 outputs，使用内存 artifact 而非强制落盘，并确保 typed artifact 在 pathless/pathful xlsx 写节点路径保留值域。 [scope-review-2026-07-20-c999]

### `workflow-observability-bridge`
- Title: workflow-observability-bridge
- Source: [workflow-observability-bridge.feature](repo:llmanspec/specs/workflow-observability-bridge/workflow-observability-bridge.feature)
- Summary: 定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约，使 demand 事件可稳定归因到 workflow 节点，并提供最小的 workflow-level 编排事件。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-preflight-runtime-only-diagnostics`
- Title: workflow-preflight-runtime-only-diagnostics
- Source: [workflow-preflight-runtime-only-diagnostics.feature](repo:llmanspec/specs/workflow-preflight-runtime-only-diagnostics/workflow-preflight-runtime-only-diagnostics.feature)
- Summary: 为 `run_workflow(...)` 增加一个 engine 执行前的 preflight 阶段,用于运行一组“runtime-only 但可推理”的诊断（v1 仅覆盖 `validate_unique_field_names`）,并以 fail-fast 的方式把错误提前暴露为 workflow compile/config error。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-replay-bundle`
- Title: workflow-replay-bundle
- Source: [workflow-replay-bundle.feature](repo:llmanspec/specs/workflow-replay-bundle/workflow-replay-bundle.feature)
- Summary: 定义 workflow 级 replay bundle 导出契约：包含 workflow scope 快照/事件流与 demand child replay 目录，支持 drill-down 引用，保持 child replay 现有协议不变。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-run-patches`
- Title: workflow-run-patches
- Source: [workflow-run-patches.feature](repo:llmanspec/specs/workflow-run-patches/workflow-run-patches.feature)
- Summary: 允许 run_workflow 接受按 workflow run id 注入的 per-run runtime patches，支持覆盖 batch_size、parallel_mode、max_workers、demand_diagnostics、components 等参数，并确保安全边界参数不可覆盖。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-runtime-module-organization`
- Title: workflow-runtime-module-organization
- Source: [workflow-runtime-module-organization.feature](repo:llmanspec/specs/workflow-runtime-module-organization/workflow-runtime-module-organization.feature)
- Summary: 定义 workflow runtime 的包位置、子模块职责划分与稳定入口策略,确保其作为 framework 层能力与 DSL 层保持清晰边界. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-runtime-quality-and-test-stability`
- Title: workflow-runtime-quality-and-test-stability
- Source: [workflow-runtime-quality-and-test-stability.feature](repo:llmanspec/specs/workflow-runtime-quality-and-test-stability/workflow-runtime-quality-and-test-stability.feature)
- Summary: 定义 workflow runtime 的质量与测试稳定性要求,包括依赖注入契约、规则 SSOT 复用与并发测试的确定性护栏. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-shared-output-containers`
- Title: workflow-shared-output-containers
- Source: [workflow-shared-output-containers.feature](repo:llmanspec/specs/workflow-shared-output-containers/workflow-shared-output-containers.feature)
- Summary: 定义 workflow 共享输出容器的资源声明、写入节点、确定性顺序、追加/合并语义、原子提交、可观测性及并发安全契约。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-sheetbook-resources`
- Title: workflow-sheetbook-resources
- Source: [workflow-sheetbook-resources.feature](repo:llmanspec/specs/workflow-sheetbook-resources/workflow-sheetbook-resources.feature)
- Summary: 定义 workflow YAML 的共享 `.xlsx` book 资源(以 `workflow.resources.books` 表达)的迁移约束与运行期契约: 确定性写入、冲突安全、可观测且可原子导出为最终 xlsx,并提供可稳定引用的内置 loader 供下游节点读取 sheet rows（不再提供 cell/sheet 预算护栏）. [scope-review-2026-07-20-c999]

### `workflow-stage-scheduling`
- Title: workflow-stage-scheduling
- Source: [workflow-stage-scheduling.feature](repo:llmanspec/specs/workflow-stage-scheduling/workflow-stage-scheduling.feature)
- Summary: 为 workflow DAG 提供可配置的调度 preset，使调用方可以在保持默认 pipeline 行为不变的前提下，选择严格的 stage barrier（阶段屏障）调度，以提升可预期性、资源规划与可解释性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-stage-scheduling-residual-risks`
- Title: workflow-stage-scheduling-residual-risks
- Source: [workflow-stage-scheduling-residual-risks.feature](repo:llmanspec/specs/workflow-stage-scheduling-residual-risks/workflow-stage-scheduling-residual-risks.feature)
- Summary: 将 `workflow stage scheduling`（`pipeline` / `stage_barrier`）相关的“残留风险”收敛为稳定、可检索、可复核的 risk register，并明确在后续迭代/验收中必须检查的边界与可观测性约束。 本 spec 不引入新的 runtime 行为；其目标是把“真实项目里可能遇到的解释偏差、下游消费破坏或性能印象落差”显式化，作为后续变更的 chec [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `workflow-versioned-outputs`
- Title: workflow-versioned-outputs
- Source: [workflow-versioned-outputs.feature](repo:llmanspec/specs/workflow-versioned-outputs/workflow-versioned-outputs.feature)
- Summary: 定义版本化输出协议（D-2）：将 `path` 解释为输出 root 目录,并在 root 下以 `versions/<version_id>/...` 写入产物,同时通过 `manifest/latest.json` 提供稳定入口与并发下的原子更新语义（last-writer-wins,但不丢历史版本）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-backend-migration`
- Title: yaml-backend-migration
- Source: [yaml-backend-migration.feature](repo:llmanspec/specs/yaml-backend-migration/yaml-backend-migration.feature)
- Summary: 定义 `scalim` 默认 YAML backend 迁移到 vendored `ruamel.yaml`(YAML 1.2) 的运行时契约, 并为 CLI 的 YAML round-trip 编辑能力建立稳定性门禁(no-op 字节级幂等 + minimal edit)。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-agent-guidance`
- Title: yaml-dsl-agent-guidance
- Source: [yaml-dsl-agent-guidance.feature](repo:llmanspec/specs/yaml-dsl-agent-guidance/yaml-dsl-agent-guidance.feature)
- Summary: 定义 `scalim-yaml-dsl` 手工维护 skill 的任务驱动组织方式,确保 agent 能基于最小入口、明确命令和按需 references 一次完成 YAML 编写、升级、校验、订正与渐进迁移方案设计. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-allowlist-policy`
- Title: yaml-dsl-allowlist-policy
- Source: [yaml-dsl-allowlist-policy.feature](repo:llmanspec/specs/yaml-dsl-allowlist-policy/yaml-dsl-allowlist-policy.feature)
- Summary: 防止allowlist配置误用导致的安全风险，包括通配符滥用、隐式逃逸口和不受信的trusted-mode启用。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-books-resources`
- Title: yaml-dsl-books-resources
- Source: [yaml-dsl-books-resources.feature](repo:llmanspec/specs/yaml-dsl-books-resources/yaml-dsl-books-resources.feature)
- Summary: 定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义. [scope-review-2026-07-12-c5-openpyxl-helpers]

### `yaml-dsl-builtin-callables`
- Title: yaml-dsl-builtin-callables
- Source: [yaml-dsl-builtin-callables.feature](repo:llmanspec/specs/yaml-dsl-builtin-callables/yaml-dsl-builtin-callables.feature)
- Summary: 为 `YAML DSL` 中的 loader/call_by/... 等 Python 可调用对象引用点提供一套 的内置 callable 引用语法,避免下游依赖 `scalim.*` 内部模块路径。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-callable-preflight`
- Title: yaml-dsl-callable-preflight
- Source: [yaml-dsl-callable-preflight.feature](repo:llmanspec/specs/yaml-dsl-callable-preflight/yaml-dsl-callable-preflight.feature)
- Summary: 定义 YAML DSL 在 demand compile / workflow preflight 阶段的 callable preflight: 在 resolver 安全边界就绪后,对用户可配置的 Python callable 执行“可推理的签名/形态/固定 contract”校验,并在失败时 fail-fast。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-cli-validation`
- Title: yaml-dsl-cli-validation
- Source: [yaml-dsl-cli-validation.feature](repo:llmanspec/specs/yaml-dsl-cli-validation/yaml-dsl-cli-validation.feature)
- Summary: 定义 CLI 校验工具的行为契约，包括校验分层、诊断输出格式与错误定位，确保 CLI 结果可用于 IDE 跳转、CI 报告与脚本化消费。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-compiler-frontend`
- Title: yaml-dsl-compiler-frontend
- Source: [yaml-dsl-compiler-frontend.feature](repo:llmanspec/specs/yaml-dsl-compiler-frontend/yaml-dsl-compiler-frontend.feature)
- Summary: 定义 YAML DSL 编译前端的两个步骤：静态编译（只解析 YAML/AST、不导入用户代码、不依赖 allowlist）与运行时链接（resolve modules + 执行 allowlist 约束）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-demand-imports-scope`
- Title: yaml-dsl-demand-imports-scope
- Source: [yaml-dsl-demand-imports-scope.feature](repo:llmanspec/specs/yaml-dsl-demand-imports-scope/yaml-dsl-demand-imports-scope.feature)
- Summary: 定义 demand imports (`imports` / `$import`) 的作用域边界，确保其仅服务于稳定的 authoring 复用场景，而非 runtime overlay 或 output extras 的替代机制。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-demo-scenarios-suite`
- Title: yaml-dsl-demo-scenarios-suite
- Source: [yaml-dsl-demo-scenarios-suite.feature](repo:llmanspec/specs/yaml-dsl-demo-scenarios-suite/yaml-dsl-demo-scenarios-suite.feature)
- Summary: 维护一组 YAML DSL 场景库（fixtures），覆盖电商/广告/客服三类域，并纳入自动化回归测试范围，确保 DSL 能力与实现持续对齐。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-docs-skills-autogen-sync`
- Title: yaml-dsl-docs-skills-autogen-sync
- Source: [yaml-dsl-docs-skills-autogen-sync.feature](repo:llmanspec/specs/yaml-dsl-docs-skills-autogen-sync/yaml-dsl-docs-skills-autogen-sync.feature)
- Summary: 确保 CLI/LSP 文档和 skill 文档从单一真相源自动生成，避免手工维护重复文案，并通过 QA gate 拦截文档漂移。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-file-resources`
- Title: yaml-dsl-file-resources
- Source: [yaml-dsl-file-resources.feature](repo:llmanspec/specs/yaml-dsl-file-resources/yaml-dsl-file-resources.feature)
- Summary: 定义 demand/workflow 统一的 `resources.files` 文件输出资源入口,并约束 CSV 输出通过 `outputs[*].to.file` + `outputs[*].write` 绑定,取代 legacy `outputs[*].container`. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-import-aliases-and-presets`
- Title: yaml-dsl-import-aliases-and-presets
- Source: [yaml-dsl-import-aliases-and-presets.feature](repo:llmanspec/specs/yaml-dsl-import-aliases-and-presets/yaml-dsl-import-aliases-and-presets.feature)
- Summary: 支持项目级配置文件治理 YAML DSL imports 路径解析，提供 alias 映射、allowed roots 约束和内置 presets 引用能力。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-imports`
- Title: yaml-dsl-imports
- Source: [yaml-dsl-imports.feature](repo:llmanspec/specs/yaml-dsl-imports/yaml-dsl-imports.feature)
- Summary: 为 demand YAML 提供跨文件复用能力: 顶层 `imports` + 的 `$import`(编译期展开),并在 schema/语义校验前完成展开. 说明: - `$import` 的允许范围以稳定 authoring surfaces 为准;详见 yaml-dsl-demand-imports-scope 规范. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-lsp-cli`
- Title: yaml-dsl-lsp-cli
- Source: [yaml-dsl-lsp-cli.feature](repo:llmanspec/specs/yaml-dsl-lsp-cli/yaml-dsl-lsp-cli.feature)
- Summary: 提供一个跨编辑器可复用的 YAML DSL LSP server 启动入口（默认 stdio），并约束其日志/降级行为， 以保证编辑器集成稳定且可排障。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-lsp-editor-integration`
- Title: yaml-dsl-lsp-editor-integration
- Source: [yaml-dsl-lsp-editor-integration.feature](repo:llmanspec/specs/yaml-dsl-lsp-editor-integration/yaml-dsl-lsp-editor-integration.feature)
- Summary: 提供一套可复制、可审计、可排障的多编辑器接入指南与回归套件，降低 YAML DSL LSP server 在各编辑器生态中的接入成本，并持续验证 editor semantics core 的行为稳定性。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-lsp-project-discovery`
- Title: yaml-dsl-lsp-project-discovery
- Source: [yaml-dsl-lsp-project-discovery.feature](repo:llmanspec/specs/yaml-dsl-lsp-project-discovery/yaml-dsl-lsp-project-discovery.feature)
- Summary: 为 LSP 提供稳定的项目发现逻辑：nearest-wins `scalim.yaml` 查找、`python_roots` 解析（dev-only）、以及 demand/workflow YAML 类型确定性分类。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-lsp-semantics-core`
- Title: yaml-dsl-lsp-semantics-core
- Source: [yaml-dsl-lsp-semantics-core.feature](repo:llmanspec/specs/yaml-dsl-lsp-semantics-core/yaml-dsl-lsp-semantics-core.feature)
- Summary: 定义 LSP 编辑器语义核心：project discovery、静态无副作用 diagnostics、Python 引用定位、光标位置抽取（call_by kwargs / compute 表达式 token），均不执行用户代码。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-lsp-server`
- Title: yaml-dsl-lsp-server
- Source: [yaml-dsl-lsp-server.feature](repo:llmanspec/specs/yaml-dsl-lsp-server/yaml-dsl-lsp-server.feature)
- Summary: 定义 YAML DSL LSP server 的语义 contract：诊断（diagnostics）与 Python 引用的 definition/hover/completion，并要求 server 侧复用 shared core， 以保证跨编辑器一致、静态无副作用且可诊断降级（不 crash、不退出、不依赖 shell-out CLI）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-observability-boundary`
- Title: yaml-dsl-observability-boundary
- Source: [yaml-dsl-observability-boundary.feature](repo:llmanspec/specs/yaml-dsl-observability-boundary/yaml-dsl-observability-boundary.feature)
- Summary: 将 observability 配置从 YAML 主线移除，迁移到 Python/CLI runtime entrypoints，并在迁移期内提供可执行的迁移警告。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-output-overrides`
- Title: yaml-dsl-output-overrides
- Source: [yaml-dsl-output-overrides.feature](repo:llmanspec/specs/yaml-dsl-output-overrides/yaml-dsl-output-overrides.feature)
- Summary: 为下游”UI 动态选字段/动态输出”场景提供单一标准做法：demand YAML 保持可复用（通常不声明 `outputs`），调用侧在 `run/compile` 时通过 typed `RunOverrides` 显式指定输出编排与 IO 覆盖。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-project-config-schema`
- Title: yaml-dsl-project-config-schema
- Source: [yaml-dsl-project-config-schema.feature](repo:llmanspec/specs/yaml-dsl-project-config-schema/yaml-dsl-project-config-schema.feature)
- Summary: 为项目级配置文件 `scalim.yaml` 提供自动生成的 JSON Schema，以获得与 demand/workflow 类似的编辑器补全与 schema-only 校验体验，并将其纳入同一条”SSOT → 生成物 → drift gate”的治理链路。 该 schema 仅描述 `scalim.yaml` 文件的结构，不改变 `scalim.yaml` 的可选性与 nearest-wins [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-public-tools`
- Title: yaml-dsl-public-tools
- Source: [yaml-dsl-public-tools.feature](repo:llmanspec/specs/yaml-dsl-public-tools/yaml-dsl-public-tools.feature)
- Summary: 为 YAML DSL 的下游集成提供稳定”工具/自省”公开入口，避免下游依赖 runtime 的内部实现模块路径。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-render-effective-yaml`
- Title: yaml-dsl-render-effective-yaml
- Source: [yaml-dsl-render-effective-yaml.feature](repo:llmanspec/specs/yaml-dsl-render-effective-yaml/yaml-dsl-render-effective-yaml.feature)
- Summary: 提供用于 review/debug/对拍的库侧 API，将”作者写的 demand YAML”渲染为 effective YAML（展开后的单文件等价配置），避免 imports/template 复用在 review 时变成黑盒。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-runtime-policy-boundary`
- Title: yaml-dsl-runtime-policy-boundary
- Source: [yaml-dsl-runtime-policy-boundary.feature](repo:llmanspec/specs/yaml-dsl-runtime-policy-boundary/yaml-dsl-runtime-policy-boundary.feature)
- Summary: 将 runtime policy 从 YAML 主线迁出到 Python/CLI runtime entrypoints，并建立清晰的 policy boundary：parser-only 路径不运行 runtime-only diagnostics；c40 起 keys 分片与粗缓存/复用策略以 typed oneof 运行入口为 SSOT（YAML 覆盖优先级显式）。 [c40-yaml-runtime-policy-boundary] [c50-source-id-graph-refs]

### `yaml-dsl-schema`
- Title: yaml-dsl-schema
- Source: [yaml-dsl-schema.feature](repo:llmanspec/specs/yaml-dsl-schema/yaml-dsl-schema.feature)
- Summary: 通过 dataclass 元数据生成 YAML DSL JSON Schema，作为校验与编辑器提示的唯一来源。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-unified-loader`
- Title: yaml-dsl-unified-loader
- Source: [yaml-dsl-unified-loader.feature](repo:llmanspec/specs/yaml-dsl-unified-loader/yaml-dsl-unified-loader.feature)
- Summary: 提供统一的 YAML load facade，确保 DSL 所有入口（CLI、runtime、workflow、imports、project config）共享相同的解析行为和错误结构。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-workflow`
- Title: yaml-dsl-workflow
- Source: [yaml-dsl-workflow.feature](repo:llmanspec/specs/yaml-dsl-workflow/yaml-dsl-workflow.feature)
- Summary: 提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目). [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-workflow-lifecycle-pipeline`
- Title: yaml-dsl-workflow-lifecycle-pipeline
- Source: [yaml-dsl-workflow-lifecycle-pipeline.feature](repo:llmanspec/specs/yaml-dsl-workflow-lifecycle-pipeline/yaml-dsl-workflow-lifecycle-pipeline.feature)
- Summary: 定义 workflow 生命周期显式阶段管线（phase pipeline）：structural preload 保持 parser-only、overrides 合并、effective outputs/resources 驱动的 preflight diagnostics、确定性的 fail-fast 顺序。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-workflow-validate`
- Title: yaml-dsl-workflow-validate
- Source: [yaml-dsl-workflow-validate.feature](repo:llmanspec/specs/yaml-dsl-workflow-validate/yaml-dsl-workflow-validate.feature)
- Summary: 提供面向 CI/预发布的 workflow-level validate CLI 入口，在不执行 workflow 的前提下对 workflow YAML 及其引用的 demands 做静态/编译期校验。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-dsl-write-policy-and-output-extras`
- Title: yaml-dsl-write-policy-and-output-extras
- Source: [yaml-dsl-write-policy-and-output-extras.feature](repo:llmanspec/specs/yaml-dsl-write-policy-and-output-extras/yaml-dsl-write-policy-and-output-extras.feature)
- Summary: 明确输出资源的四层边界：resources 声明、write_defaults 策略、outputs 内容编排、runtime output extras（meta/audit），并将 write policy 和 extras 迁出 YAML 主线。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]

### `yaml-template-vars`
- Title: yaml-template-vars
- Source: [yaml-template-vars.feature](repo:llmanspec/specs/yaml-template-vars/yaml-template-vars.feature)
- Summary: 定义 YAML 模板变量预编译能力：在 YAML parse 前通过 LiteJinja2 渲染 `{{ x }}`/`{% ... %}` 占位符，并提供安全的 sandbox 策略与输入护栏。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
