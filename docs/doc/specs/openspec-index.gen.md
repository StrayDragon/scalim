<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `openspec/specs/*/spec.md`
-->

??? warning "自动生成文件"
    本文件由 `scripts/gen-docs.py` 自动生成，请勿手动编辑。如需修改，请编辑源文件或生成脚本。

# OpenSpec 索引(生成)

说明:
- 本页仅做“索引与链接”,不把 `openspec/specs/**` 作为站点页面.
- 规范本体以仓库文件为准,请通过代码链接打开.

## Specs

### `cli-yaml-dsl-viz-compile`
- Title: cli-yaml-dsl-viz-compile Specification
- Source: [spec.md](#code=openspec/specs/cli-yaml-dsl-viz-compile/spec.md)
- Summary: TBD - created by archiving change c0-yaml-dsl-viz-compile-cli. Update Purpose after archive.

### `demand-dsl`
- Title: demand-dsl Specification
- Source: [spec.md](#code=openspec/specs/demand-dsl/spec.md)
- Summary: 实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.

### `dsl-runtime-structure`
- Title: dsl-runtime-structure Specification
- Source: [spec.md](#code=openspec/specs/dsl-runtime-structure/spec.md)
- Summary: 定义 YAML DSL runtime 作为 DSL adapter/编译器的边界与对外入口，明确 YAML 配置（outputs/可观测性/retry 等）在编译期映射为 DSL-agnostic 运行请求对象的规则。

### `examples-marimo`
- Title: marimo-examples Specification
- Source: [spec.md](#code=openspec/specs/examples-marimo/spec.md)
- Summary: 定义仓库内 Marimo 示例/教学套件治理边界：Marimo notebooks 作为唯一交互载体，headless runner/pytest 作为确定性回归入口，要求执行真相来源位于 notebooks（同源复用）。

### `execution-adaptive-guardrails`
- Title: execution-adaptive-guardrails Specification
- Source: [spec.md](#code=openspec/specs/execution-adaptive-guardrails/spec.md)
- Summary: TBD - created by archiving change c0-deps-and-adaptive-guardrails. Update Purpose after archive.

### `execution-call-by-memoization`
- Title: execution-call-by-memoization Specification
- Source: [spec.md](#code=openspec/specs/execution-call-by-memoization/spec.md)
- Summary: TBD - created by archiving change c20-exp-call-by-memoize-field-policy. Update Purpose after archive.

### `execution-concurrency-safety`
- Title: no-external-callback-under-lock Specification
- Source: [spec.md](#code=openspec/specs/execution-concurrency-safety/spec.md)
- Summary: 为执行层的并发安全定义护栏：任何可能触发用户回调（hooks/observers）或外部回调的操作不得在内部互斥锁临界区内执行，避免重入/锁顺序反转导致的死锁。

### `execution-dense-batch`
- Title: Dense Batch Context Specification
- Source: [spec.md](#code=openspec/specs/execution-dense-batch/spec.md)
- Summary: 优化批次执行场景的内存占用与访问速度，通过 Dense 存储表示支持连续整数 row_id 的紧凑编码。

### `execution-derived-outputs`
- Title: derived-outputs Specification
- Source: [spec.md](#code=openspec/specs/execution-derived-outputs/spec.md)
- Summary: **状态: ⚠️ 实验性** 支持在同一次运行中基于详情行流生成派生输出(增量聚合 + finalize 阶段输出),并定义 IR/Python-only 配置入口、资源护栏与 `adaptive` 并发边界.

### `execution-error-taxonomy`
- Title: error-taxonomy Specification
- Source: [spec.md](#code=openspec/specs/execution-error-taxonomy/spec.md)
- Summary: **状态: ✅ 已实现** 为 scalim 建立统一的异常体系规范:以 ScalimError 作为唯一根,并在其下按域拆分子类;对用户可感知错误以异常类型/显式字段作为稳定契约;同时约束错误事件的最小输出与敏感信息治理,并提供可执行的测试断言口径.

### `execution-hotpath-fastpaths`
- Title: execution-hotpath-fastpaths Specification
- Source: [spec.md](#code=openspec/specs/execution-hotpath-fastpaths/spec.md)
- Summary: 在不要求业务改动的前提下，降低 execution 热路径（`compute` / `call_by` / `load_ref`）的 per-row 固定开销，并保持既有语义、可观测性与低内存特性。

### `execution-loader-retry`
- Title: loader-retry-policy Specification
- Source: [spec.md](#code=openspec/specs/execution-loader-retry/spec.md)
- Summary: 提供可配置的 loader retry policy 机制，在 loader 调用因瞬态错误失败时执行有限的自动重试，支持全局默认策略与 per-source 覆盖，并通过可配置的退避策略、次数上限和耗时上限防止无限重试。

### `execution-micro-tunes`
- Title: execution-micro-tunes Specification
- Source: [spec.md](#code=openspec/specs/execution-micro-tunes/spec.md)
- Summary: 定义 YAML DSL 语法增强，简化常见场景的表达复杂度，包括 relation 引用语法糖、output.fields 简写、runtime vars 指令节点形式，以及改进的验证器诊断信息。

### `execution-output-composition`
- Title: output-composition Specification
- Source: [spec.md](#code=openspec/specs/execution-output-composition/spec.md)
- Summary: **状态: ✅ 已实现** 支持单次运行的多输出目标组合(多文件或同一容器多逻辑输出),并定义容器命名冲突策略与输出失败策略(`failure_policy`).

### `execution-preload-cache`
- Title: execution-preload-cache Specification
- Source: [spec.md](#code=openspec/specs/execution-preload-cache/spec.md)
- Summary: 定义 `PreloadCache` 的完整行为契约：并发安全性、in-flight 去重、signature 冲突防护、诊断能力，以及并发场景下的幂等性期望。

### `execution-ref-miss-default-cases`
- Title: execution-ref-miss-default-cases Specification
- Source: [spec.md](#code=openspec/specs/execution-ref-miss-default-cases/spec.md)
- Summary: 定义 YAML DSL 中 source ref 字段的 relation miss 默认值机制。允许用户在关联查询未命中时使用有序的默认值替代 None，提高配置表达能力和错误容错性。

### `execution-safety-single-writer`
- Title: single-writer-model-safety Specification
- Source: [spec.md](#code=openspec/specs/execution-safety-single-writer/spec.md)
- Summary: Establish and enforce a single-writer threading model for workflow execution state, ensuring that write operations to shared runtime structures are either owned by a controller thread or protected by locks in free-threaded Python runtimes, with debug assertions to catch violations early.

### `execution-source-cache`
- Title: source-cache Specification
- Source: [spec.md](#code=openspec/specs/execution-source-cache/spec.md)
- Summary: **状态: ✅ 已实现** 支持 `cache_mode=preload_forever` 的数据源在 pipeline 启动前预加载,结果写入 `ExecutionRuntime.preloaded_cache` 并在关联加载时复用;计划元数据记录已缓存的数据源。对于高频且内存占用小的映射表(如国家地区表、枚举常量映射表),作为全局一次性导入使用以加速获值速度。

### `execution-structure`
- Title: execution-structure Specification
- Source: [spec.md](#code=openspec/specs/execution-structure/spec.md)
- Summary: 定义 execution 层的模块拆分与入口契约,并明确统一 IR 编排入口(如 `run_ir`)的边界,确保执行编排对 DSL 配置解耦且行为在重构后保持兼容.

### `governance-docs`
- Title: doc-governance Specification
- Source: [spec.md](#code=openspec/specs/governance-docs/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库内文档的分层、生成边界(`*.gen.*` + `AUTOGEN` 注入区块)、统一生成入口与漂移门禁,以降低维护成本并防止”手工修改生成物/区块”导致的不一致.

### `governance-docs-site`
- Title: docs-site Specification
- Source: [spec.md](#code=openspec/specs/governance-docs-site/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库内文档站点的范围与组织规则：使用 Zensical（兼容 MkDocs 的配置格式）构建站点，以 `docs/doc/` 作为唯一文档真源，避免将规范、审计报告等纳入站点。

### `governance-extension-points`
- Title: explicit-extension-points Specification
- Source: [spec.md](#code=openspec/specs/governance-extension-points/spec.md)
- Summary: **状态: ✅ 已实现** 定义 PROJECT_NAME 内部扩展点的显式注入与编译式分发模型，减少模块级”魔法注入”与事件热路径反射，提升类型友好性、可维护性与性能稳定性。

### `governance-mainline-principles`
- Title: governance-mainline-principles Specification
- Source: [spec.md](#code=openspec/specs/governance-mainline-principles/spec.md)
- Summary: 定义 YAML DSL 的上位主线原则与设计护栏，用于约束后续变更的方向与评审口径：单主线原地演进、authoring/runtime policy 分离、KV-first、以及 workflow 小而声明式（拒绝 imports expansion）。

### `governance-misc`
- Title: misc Specification
- Source: [spec.md](#code=openspec/specs/governance-misc/spec.md)
- Summary: **状态: ✅ 已实现** 为“重构分析类文档”提供统一的规范入口与最低要求,确保依赖分析、边界说明、任务拆分、验证口径和约束声明一致,以便在不改动代码的前提下形成可复核的决策依据.

### `governance-module-organization`
- Title: module-organization Specification
- Source: [spec.md](#code=openspec/specs/governance-module-organization/spec.md)
- Summary: **状态: ✅ 已实现** 定义运行时模块的边界、入口最小化与依赖约束,避免将内部实现路径误用为公共 API,并保持模块层级单向依赖与 Python 3.6 运行时兼容性.

### `governance-package-identity`
- Title: package-identity Specification
- Source: [spec.md](#code=openspec/specs/governance-package-identity/spec.md)
- Summary: 定义项目包身份与分发边界的治理规范，确保 PyPI 发行名、导入根包名、CLI 命令名之间的清晰分离，以及运行时主包与 CLI 发行物的版本约束解耦。

### `governance-public-api`
- Title: public-api-governance Specification
- Source: [spec.md](#code=openspec/specs/governance-public-api/spec.md)
- Summary: **状态: ✅ 已实现** 定义 public API 边界治理规则：稳定入口编目、`__all__` 治理、用户材料导入边界、agent skill 生成器，确保在不引入"符号级硬 manifest SSOT"的前提下维护清晰的公共契约。

### `hooks-events`
- Title: hooks-events Specification
- Source: [spec.md](#code=openspec/specs/hooks-events/spec.md)
- Summary: 定义 hooks 和事件系统的事件类型和策略决策信号规范,包括 loader retry 事件和 policy decision signals。

### `hooks-observability-structure`
- Title: hooks-observability-structure Specification
- Source: [spec.md](#code=openspec/specs/hooks-observability-structure/spec.md)
- Summary: 定义 Hook/Observer/事件体系的统一边界:事件契约、分发路径、组件装配与高频路径性能语义.

### `ir-field-compute`
- Title: field-compute Specification
- Source: [spec.md](#code=openspec/specs/ir-field-compute/spec.md)
- Summary: **状态: ✅ 已实现** 定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略.

### `ir-key-normalization`
- Title: key-normalization Specification
- Source: [spec.md](#code=openspec/specs/ir-key-normalization/spec.md)
- Summary: `key_normalization` 提供一个运行期可控的”稳定字符串口径”键匹配策略,用于解决 relations/derived outputs 中跨来源类型不一致导致的 miss/分组拆分问题(例如 `1` 与 `”1”`). 该能力为 `EXPERIMENTAL`,默认关闭(`raw`).

### `ir-source-relations`
- Title: source-relations Specification
- Source: [spec.md](#code=openspec/specs/ir-source-relations/spec.md)
- Summary: **状态: ✅ 已实现** 使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义.

### `ir-structure`
- Title: ir-structure Specification
- Source: [spec.md](#code=openspec/specs/ir-structure/spec.md)
- Summary: 定义 IR 层的纯数据边界与依赖约束,确保 spec/ir 不依赖执行与规划层,便于稳定复用、演进与测试.

### `observability-flow-visualization`
- Title: flow-visualization Specification
- Source: [spec.md](#code=openspec/specs/observability-flow-visualization/spec.md)
- Summary: **状态: ✅ 已实现** - VizGraphSnapshot + VizEventStream 可视化机制已实现 提供执行过程的可视化输出:VizGraphSnapshot 从 ExecutionPlan 生成 XYFlow 兼容的 nodes/edges 结构用于依赖图展示;VizEventStream 将 Hook 事件映射为可视化事件流支持离线回放.

### `observability-logging`
- Title: framework-logging Specification
- Source: [spec.md](#code=openspec/specs/observability-logging/spec.md)
- Summary: **状态: ✅ 已实现** 为框架内部日志建立统一的 Python 标准库 `logging` 使用约定,以保证默认静默、命名空间稳定、输出前缀一致,并提供可扩展的诊断字段与 context 绑定机制。

### `observability-observer-concurrency`
- Title: observer-concurrency-contract Specification
- Source: [spec.md](#code=openspec/specs/observability-observer-concurrency/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow 并发执行时 observers/hooks/components 的默认并发语义,确保在不要求 observer 实现方线程安全的前提下仍具备可解释、可复现的事件回放顺序,并保持 `no-external-callback-under-lock` 护栏不被破坏.

### `output-mode-api`
- Title: output-mode-api Specification
- Source: [spec.md](#code=openspec/specs/output-mode-api/spec.md)
- Summary: 定义运行时输出语义为"显式 sink 驱动": 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理.

### `output-sink-contracts`
- Title: sinks-contracts Specification
- Source: [spec.md](#code=openspec/specs/output-sink-contracts/spec.md)
- Summary: 定义 sink 接口稳定性与可选依赖提示规范，确保内建与外部 sink 的长期兼容、可诊断性与一致行为。

### `output-sink-fastpath`
- Title: sink-fastpath Specification
- Source: [spec.md](#code=openspec/specs/output-sink-fastpath/spec.md)
- Summary: TBD - created by archiving change c60-performance-optimization-abc. Update Purpose after archive.

### `parallel-execution`
- Title: parallel-execution Specification
- Source: [spec.md](#code=openspec/specs/parallel-execution/spec.md)
- Summary: 定义执行层对外并发语义 `seq|adaptive`,以及 `adaptive` 下的调度边界、后端选择、结果提交与事件回放契约.

### `performance-observability`
- Title: performance-observability Specification
- Source: [spec.md](#code=openspec/specs/performance-observability/spec.md)
- Summary: PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.

### `planning-deterministic-ordering`
- Title: deterministic-ordering Specification
- Source: [spec.md](#code=openspec/specs/planning-deterministic-ordering/spec.md)
- Summary: 定义 PROJECT_NAME 的稳定顺序最小契约，用于保证 planning/执行在相同输入下可复现，并避免 `PYTHONHASHSEED` 等非确定性因素影响结果。 本 spec 覆盖执行计划构建顺序、拓扑排序输出的 tie-break 规则、以及 keys 绑定列表的稳定顺序要求。

### `quality-benchmarking`
- Title: benchmarking Specification
- Source: [spec.md](#code=openspec/specs/quality-benchmarking/spec.md)
- Summary: 定义基准测试入口与依赖约束，覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析。

### `quality-perf-regression`
- Title: perf-regression-guardrails Specification
- Source: [spec.md](#code=openspec/specs/quality-perf-regression/spec.md)
- Summary: 定义性能回归护栏、基准测试套件与内存剖析入口，确保执行热路径的确定性行为不被退化，并提供可测量的趋势指标。

### `runtime-guardrails`
- Title: runtime-guardrails Specification
- Source: [spec.md](#code=openspec/specs/runtime-guardrails/spec.md)
- Summary: 定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录.

### `runtime-policy-normalization`
- Title: runtime-policy-normalization Specification
- Source: [spec.md](#code=openspec/specs/runtime-policy-normalization/spec.md)
- Summary: TBD - created by archiving change c6-policy-normalization-breaking-cleanup. Update Purpose after archive.

### `runtime-pruning`
- Title: runtime-pruning Specification
- Source: [spec.md](#code=openspec/specs/runtime-pruning/spec.md)
- Summary: PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.

### `streaming-output`
- Title: streaming-output Specification
- Source: [spec.md](#code=openspec/specs/streaming-output/spec.md)
- Summary: 支持 IRowSink 与 IColumnSink 的流式写入路径,定义 main source 行流、分批与 `row_id` 规则,并约束行式路径"行就绪即写出 + rows 绑定 release 屏障"语义.

### `structured-logging`
- Title: structured-logging Specification
- Source: [spec.md](#code=openspec/specs/structured-logging/spec.md)
- Summary: 定义结构化日志的 JSONL 输出格式、字段元信息、归因上下文自动注入及 CLI 渲染能力，确保日志可被机器解析与人类友好展示。

### `testing-quality`
- Title: testing-quality Specification
- Source: [spec.md](#code=openspec/specs/testing-quality/spec.md)
- Summary: 定义测试分类、覆盖率门槛与 demo 对拍验证的最低要求,明确默认测试范围与质量门禁,确保持续集成结果稳定可复现.

### `tests-domain-suites`
- Title: tests-domain-suites Specification
- Source: [spec.md](#code=openspec/specs/tests-domain-suites/spec.md)
- Summary: 将测试按领域组织为显式套件目录，约束 YAML string-reference fixtures 放在 tests/fixtures/，禁止 additional 模式，并确保 governance 聚焦于契约测试和脚本单元测试。

### `tools-agent-skill-export`
- Title: agent-skill-export Specification
- Source: [spec.md](#code=openspec/specs/tools-agent-skill-export/spec.md)
- Summary: 定义 `scalim-yaml-dsl` skill 自动生成器的职责边界，确保自动化只负责受控参考产物，同时保证输出可校验、可重建、不会覆盖手工维护的 skill 本体。

### `tools-console-reports`
- Title: dependency-free-console-reports Specification
- Source: [spec.md](#code=openspec/specs/tools-console-reports/spec.md)
- Summary: TBD - created by archiving change c2-remove-literich. Update Purpose after archive.

### `tools-prompt-eval-cli`
- Title: prompt-eval-fixture-cli Specification
- Source: [spec.md](#code=openspec/specs/tools-prompt-eval-cli/spec.md)
- Summary: 定义 prompt-eval coding-agent workspace 的 fixture CLI 隔离策略，确保其不覆盖仓库真实 `scalim-cli`，同时保持 workspace 内 `uv run scalim-cli ...` 命令模板可复现，并避免对 PyPI build 依赖/网络造成的 dry-run 波动。

### `tools-prompt-eval-workflow`
- Title: prompt-eval-workflow Specification
- Source: [spec.md](#code=openspec/specs/tools-prompt-eval-workflow/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库级 prompt 评测/回归工作流的最低要求,用于守护关键 skill/指令文本的质量与文档治理边界规则,并提供稳定的本地运行入口与 CI 产物。

### `tools-resources-discovery`
- Title: resources-discovery Specification
- Source: [spec.md](#code=openspec/specs/tools-resources-discovery/spec.md)
- Summary: **状态: ✅ 已实现** 定义面向用户的稳定公开入口,用于从 output root 定位“最新一次成功发布”的产物集合(books/files),并隐藏底层 D-2 版本化输出协议的内部落盘细节.

### `vendor-dataclassesx`
- Title: dataclassesx-vendor Specification
- Source: [spec.md](#code=openspec/specs/vendor-dataclassesx/spec.md)
- Summary: **状态: ✅ 已实现** 为 `scalim/` 提供一个可 vendors 化、可审计的 dataclasses 能力入口,在保持 Python 3.6 运行时兼容的同时避免依赖外部 `dataclasses` backport,并避免包内绝对导入在多份包共存时混入错误实现。

### `vendor-legacy-sync`
- Title: legacy-vendors-sync Specification
- Source: [spec.md](#code=openspec/specs/vendor-legacy-sync/spec.md)
- Summary: **状态: ✅ 已实现** 为下游采用 `vendors/libs/` 导入链路的旧工程提供一个可审计、可重复的同步入口,用于将本仓库的 `src/scalim/` vendors 化后镜像到目标 `<vendors/libs>/scalim/`。默认仅预览(dry-run),并在显式确认时执行实际同步。

### `workflow-cache-pool`
- Title: workflow-cache-pool Specification
- Source: [spec.md](#code=openspec/specs/workflow-cache-pool/spec.md)
- Summary: 提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件/并发安全确保"复用正确且可诊断".

### `workflow-execute-organization`
- Title: workflow-execute-organization Specification
- Source: [spec.md](#code=openspec/specs/workflow-execute-organization/spec.md)
- Summary: TBD - created by archiving change c45-refactor-execute-controller-phase1. Update Purpose after archive.

### `workflow-intermediate-store`
- Title: workflow-intermediate-store Specification
- Source: [spec.md](#code=openspec/specs/workflow-intermediate-store/spec.md)
- Summary: TBD - created by archiving change c15-workflow-intermediate-store-optimizations. Update Purpose after archive.

### `workflow-ir`
- Title: workflow-ir Specification
- Source: [spec.md](#code=openspec/specs/workflow-ir/spec.md)
- Summary: 定义 Workflow IR 作为 workflow 的统一底座,并将 workflow 的 authoring surface(例如 YAML)视为"编译到 IR 的语法前端",而不是直接驱动执行器分支逻辑.

### `workflow-managed-temp-outputs`
- Title: workflow-managed-temp-outputs Specification
- Source: [spec.md](#code=openspec/specs/workflow-managed-temp-outputs/spec.md)
- Summary: 允许 workflow 托管仅供写入节点消费的中间态 outputs，使用内存 artifact 而非强制落盘，并确保 typed artifact 在 xlsx_memory 路径保留值域。

### `workflow-observability-bridge`
- Title: workflow-observability-bridge Specification
- Source: [spec.md](#code=openspec/specs/workflow-observability-bridge/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约，使 demand 事件可稳定归因到 workflow 节点，并提供最小的 workflow-level 编排事件。

### `workflow-preflight-runtime-only-diagnostics`
- Title: workflow-preflight-runtime-only-diagnostics Specification
- Source: [spec.md](#code=openspec/specs/workflow-preflight-runtime-only-diagnostics/spec.md)
- Summary: **状态: ✅ 已实现** 为 `run_workflow(...)` 增加一个 engine 执行前的 preflight 阶段,用于运行一组“runtime-only 但可推理”的诊断（v1 仅覆盖 `validate_unique_field_names`）,并以 fail-fast 的方式把错误提前暴露为 workflow compile/config error。

### `workflow-replay-bundle`
- Title: workflow-replay-bundle Specification
- Source: [spec.md](#code=openspec/specs/workflow-replay-bundle/spec.md)
- Summary: TBD - created by archiving change c10-workflow-viz-linked-replay. Update Purpose after archive.

### `workflow-run-patches`
- Title: workflow-run-patches Specification
- Source: [spec.md](#code=openspec/specs/workflow-run-patches/spec.md)
- Summary: 允许 run_workflow 接受按 workflow run id 注入的 per-run runtime patches，支持覆盖 batch_size、parallel_mode、max_workers、demand_diagnostics、components 等参数，并确保安全边界参数不可覆盖。

### `workflow-runtime-module-organization`
- Title: workflow-runtime-module-organization Specification
- Source: [spec.md](#code=openspec/specs/workflow-runtime-module-organization/spec.md)
- Summary: 定义 workflow runtime 的包位置、子模块职责划分与稳定入口策略,确保其作为 framework 层能力与 DSL 层保持清晰边界.

### `workflow-runtime-quality-and-test-stability`
- Title: workflow-runtime-quality-and-test-stability Specification
- Source: [spec.md](#code=openspec/specs/workflow-runtime-quality-and-test-stability/spec.md)
- Summary: 定义 workflow runtime 的质量与测试稳定性要求,包括依赖注入契约、规则 SSOT 复用与并发测试的确定性护栏.

### `workflow-shared-output-containers`
- Title: workflow-shared-output-containers Specification
- Source: [spec.md](#code=openspec/specs/workflow-shared-output-containers/spec.md)
- Summary: 定义 workflow 共享输出容器的资源声明、写入节点、确定性顺序、追加/合并语义、原子提交、可观测性及并发安全契约。

### `workflow-sheetbook-resources`
- Title: workflow-sheetbook-resources Specification
- Source: [spec.md](#code=openspec/specs/workflow-sheetbook-resources/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow YAML 的共享 `.xlsx` book 资源(以 `workflow.resources.books` 表达)的迁移约束与运行期契约: 预算护栏、确定性写入、冲突安全、可观测且可原子导出为最终 xlsx,并提供可稳定引用的内置 loader 供下游节点读取 sheet rows.

### `workflow-stage-scheduling`
- Title: workflow-stage-scheduling Specification
- Source: [spec.md](#code=openspec/specs/workflow-stage-scheduling/spec.md)
- Summary: **状态: ✅ 已实现** 为 workflow DAG 提供可配置的调度 preset，使调用方可以在保持默认 pipeline 行为不变的前提下，选择严格的 stage barrier（阶段屏障）调度，以提升可预期性、资源规划与可解释性。

### `workflow-stage-scheduling-residual-risks`
- Title: workflow-stage-scheduling-residual-risks Specification
- Source: [spec.md](#code=openspec/specs/workflow-stage-scheduling-residual-risks/spec.md)
- Summary: 将 `workflow stage scheduling`（`pipeline` / `stage_barrier`）相关的“残留风险”收敛为稳定、可检索、可复核的 risk register，并明确在后续迭代/验收中必须检查的边界与可观测性约束。 本 spec 不引入新的 runtime 行为；其目标是把“真实项目里可能遇到的解释偏差、下游消费破坏或性能印象落差”显式化，作为后续变更的 checklist。

### `workflow-versioned-outputs`
- Title: workflow-versioned-outputs Specification
- Source: [spec.md](#code=openspec/specs/workflow-versioned-outputs/spec.md)
- Summary: **状态: ✅ 已实现** 定义版本化输出协议（D-2）：将 `path` 解释为输出 root 目录,并在 root 下以 `versions/<version_id>/...` 写入产物,同时通过 `manifest/latest.json` 提供稳定入口与并发下的原子更新语义（last-writer-wins,但不丢历史版本）。

### `yaml-backend-migration`
- Title: yaml-backend-migration Specification
- Source: [spec.md](#code=openspec/specs/yaml-backend-migration/spec.md)
- Summary: 定义 `scalim` 默认 YAML backend 迁移到 vendored `ruamel.yaml`(YAML 1.2) 的运行时契约, 并为 CLI 的 YAML round-trip 编辑能力建立稳定性门禁(no-op 字节级幂等 + minimal edit)。

### `yaml-dsl-agent-guidance`
- Title: yaml-dsl-agent-guidance Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-agent-guidance/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `scalim-yaml-dsl` 手工维护 skill 的任务驱动组织方式,确保 agent 能基于最小入口、明确命令和按需 references 一次完成 YAML 编写、升级、校验、订正与渐进迁移方案设计.

### `yaml-dsl-allowlist-policy`
- Title: yaml-dsl-allowlist-policy Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-allowlist-policy/spec.md)
- Summary: 防止allowlist配置误用导致的安全风险，包括通配符滥用、隐式逃逸口和不受信的trusted-mode启用。

### `yaml-dsl-books-resources`
- Title: yaml-dsl-books-resources Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-books-resources/spec.md)
- Summary: 定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义.

### `yaml-dsl-builtin-callables`
- Title: yaml-dsl-builtin-callables Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-builtin-callables/spec.md)
- Summary: 为 `YAML DSL` 中的 loader/call_by/... 等 Python 可调用对象引用点提供一套 **稳定、受控、无需扩大 allowlist** 的内置 callable 引用语法,避免下游依赖 `scalim.*` 内部模块路径。

### `yaml-dsl-callable-preflight`
- Title: yaml-dsl-callable-preflight Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-callable-preflight/spec.md)
- Summary: **状态: ✅ 已实现** 定义 YAML DSL 在 demand compile / workflow preflight 阶段的 callable preflight: 在 resolver 安全边界就绪后,对用户可配置的 Python callable 执行“可推理的签名/形态/固定 contract”校验,并在失败时 fail-fast。

### `yaml-dsl-cli-validation`
- Title: yaml-dsl-cli-validation Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-cli-validation/spec.md)
- Summary: 定义 CLI 校验工具的行为契约，包括校验分层、诊断输出格式与错误定位，确保 CLI 结果可用于 IDE 跳转、CI 报告与脚本化消费。

### `yaml-dsl-compiler-frontend`
- Title: yaml-dsl-compiler-frontend Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-compiler-frontend/spec.md)
- Summary: TBD - created by archiving change c30-yaml-dsl-compiler-frontend. Update Purpose after archive.

### `yaml-dsl-demand-imports-scope`
- Title: yaml-dsl-demand-imports-scope Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-demand-imports-scope/spec.md)
- Summary: 定义 demand imports (`imports` / `$import`) 的作用域边界，确保其仅服务于稳定的 authoring 复用场景，而非 runtime overlay 或 output extras 的替代机制。

### `yaml-dsl-demo-scenarios-suite`
- Title: yaml-dsl-demo-scenarios-suite Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-demo-scenarios-suite/spec.md)
- Summary: 维护一组 YAML DSL 场景库（fixtures），覆盖电商/广告/客服三类域，并纳入自动化回归测试范围，确保 DSL 能力与实现持续对齐。

### `yaml-dsl-docs-skills-autogen-sync`
- Title: yaml-dsl-docs-skills-autogen-sync Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-docs-skills-autogen-sync/spec.md)
- Summary: 确保 CLI/LSP 文档和 skill 文档从单一真相源自动生成，避免手工维护重复文案，并通过 QA gate 拦截文档漂移。

### `yaml-dsl-file-resources`
- Title: yaml-dsl-file-resources Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-file-resources/spec.md)
- Summary: **状态: ✅ 已实现** 定义 demand/workflow 统一的 `resources.files` 文件输出资源入口,并约束 CSV 输出通过 `outputs[*].to.file` + `outputs[*].write` 绑定,取代 legacy `outputs[*].container`.

### `yaml-dsl-import-aliases-and-presets`
- Title: yaml-dsl-import-aliases-and-presets Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-import-aliases-and-presets/spec.md)
- Summary: 支持项目级配置文件治理 YAML DSL imports 路径解析，提供 alias 映射、allowed roots 约束和内置 presets 引用能力。

### `yaml-dsl-imports`
- Title: yaml-dsl-imports Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-imports/spec.md)
- Summary: **状态: ✅ 已实现** 为 demand YAML 提供跨文件复用能力: 顶层 `imports` + **受 scope 限制**的 `$import`(编译期展开),并在 schema/语义校验前完成展开. 说明: - `$import` 的允许范围以稳定 authoring surfaces 为准;详见 yaml-dsl-demand-imports-scope 规范.

### `yaml-dsl-lsp-cli`
- Title: yaml-dsl-lsp-serve Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-lsp-cli/spec.md)
- Summary: 提供一个跨编辑器可复用的 YAML DSL LSP server 启动入口（默认 stdio），并约束其日志/降级行为， 以保证编辑器集成稳定且可排障。

### `yaml-dsl-lsp-editor-integration`
- Title: yaml-dsl-editor-integration Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-lsp-editor-integration/spec.md)
- Summary: 提供一套可复制、可审计、可排障的多编辑器接入指南与回归套件，降低 YAML DSL LSP server 在各编辑器生态中的接入成本，并持续验证 editor semantics core 的行为稳定性。

### `yaml-dsl-lsp-project-discovery`
- Title: yaml-dsl-editor-project-discovery Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-lsp-project-discovery/spec.md)
- Summary: TBD - created by archiving change c999-yaml-dsl-lsp. Update Purpose after archive.

### `yaml-dsl-lsp-semantics-core`
- Title: yaml-dsl-editor-semantics-core Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-lsp-semantics-core/spec.md)
- Summary: TBD - created by archiving change c50-yaml-dsl-editor-semantics-lsp-core. Update Purpose after archive.

### `yaml-dsl-lsp-server`
- Title: yaml-dsl-lsp-server Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-lsp-server/spec.md)
- Summary: 定义 YAML DSL LSP server 的语义 contract：诊断（diagnostics）与 Python 引用的 definition/hover/completion，并要求 server 侧复用 shared core， 以保证跨编辑器一致、静态无副作用且可诊断降级（不 crash、不退出、不依赖 shell-out CLI）。

### `yaml-dsl-observability-boundary`
- Title: yaml-dsl-observability-boundary Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-observability-boundary/spec.md)
- Summary: 将 observability 配置从 YAML 主线移除，迁移到 Python/CLI runtime entrypoints，并在迁移期内提供可执行的迁移警告。

### `yaml-dsl-output-overrides`
- Title: yaml-dsl-output-overrides Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-output-overrides/spec.md)
- Summary: **状态: ✅ 已实现** 为下游”UI 动态选字段/动态输出”场景提供单一标准做法：demand YAML 保持可复用（通常不声明 `outputs`），调用侧在 `run/compile` 时通过 typed `RunOverrides` 显式指定输出编排与 IO 覆盖。

### `yaml-dsl-project-config-schema`
- Title: yaml-dsl-project-config-schema Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-project-config-schema/spec.md)
- Summary: 为项目级配置文件 `scalim.yaml` 提供自动生成的 JSON Schema，以获得与 demand/workflow 类似的编辑器补全与 schema-only 校验体验，并将其纳入同一条”SSOT → 生成物 → drift gate”的治理链路。 该 schema 仅描述 **单个** `scalim.yaml` 文件的结构，不改变 `scalim.yaml` 的可选性与 nearest-wins discovery 语义。

### `yaml-dsl-public-tools`
- Title: yaml-dsl-public-tools Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-public-tools/spec.md)
- Summary: 为 YAML DSL 的下游集成提供稳定”工具/自省”公开入口，避免下游依赖 runtime 的内部实现模块路径。

### `yaml-dsl-render-effective-yaml`
- Title: yaml-dsl-render-effective-yaml Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-render-effective-yaml/spec.md)
- Summary: **状态: ✅ 已实现** 提供用于 review/debug/对拍的库侧 API，将”作者写的 demand YAML”渲染为 effective YAML（展开后的单文件等价配置），避免 imports/template 复用在 review 时变成黑盒。

### `yaml-dsl-runtime-policy-boundary`
- Title: yaml-dsl-runtime-policy-boundary Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-runtime-policy-boundary/spec.md)
- Summary: 将 runtime policy 从 YAML 主线迁出到 Python/CLI runtime entrypoints，并建立清晰的 policy boundary：parser-only 路径不运行 runtime-only diagnostics，runtime-only diagnostics 仅在具备 effective runtime policy 的边界运行。

### `yaml-dsl-schema`
- Title: yaml-dsl-schema Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-schema/spec.md)
- Summary: **状态: ✅ 已实现** 通过 dataclass 元数据生成 YAML DSL JSON Schema，作为校验与编辑器提示的唯一来源。

### `yaml-dsl-schema-workflow-alignment`
- Title: yaml-dsl-schema-workflow-alignment Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-schema-workflow-alignment/spec.md)
- Summary: 对齐 workflow `workflow.resources` 的 schema/runtime 契约（禁止 `$import` 暴露并提供迁移提示），并为 schema numeric constraints 引入生成期 fail-fast 与仓库级 drift gate。

### `yaml-dsl-unified-loader`
- Title: yaml-dsl-unified-loader Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-unified-loader/spec.md)
- Summary: 提供统一的 YAML load facade，确保 DSL 所有入口（CLI、runtime、workflow、imports、project config）共享相同的解析行为和错误结构。

### `yaml-dsl-workflow`
- Title: yaml-dsl-workflow Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-workflow/spec.md)
- Summary: **状态: ✅ 已实现** 提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).

### `yaml-dsl-workflow-lifecycle-pipeline`
- Title: yaml-dsl-workflow-lifecycle-pipeline Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-workflow-lifecycle-pipeline/spec.md)
- Summary: TBD - created by archiving change c0-yaml-dsl-workflow-lifecycle-pipeline. Update Purpose after archive.

### `yaml-dsl-workflow-validate`
- Title: yaml-dsl-workflow-validate Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-workflow-validate/spec.md)
- Summary: 提供面向 CI/预发布的 workflow-level validate CLI 入口，在不执行 workflow 的前提下对 workflow YAML 及其引用的 demands 做静态/编译期校验。

### `yaml-dsl-write-policy-and-output-extras`
- Title: yaml-dsl-write-policy-and-output-extras Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-write-policy-and-output-extras/spec.md)
- Summary: 明确输出资源的四层边界：resources 声明、write_defaults 策略、outputs 内容编排、runtime output extras（meta/audit），并将 write policy 和 extras 迁出 YAML 主线。

### `yaml-template-vars`
- Title: yaml-template-vars Specification
- Source: [spec.md](#code=openspec/specs/yaml-template-vars/spec.md)
- Summary: 定义 YAML 模板变量预编译能力：在 YAML parse 前通过 LiteJinja2 渲染 `{{ x }}`/`{% ... %}` 占位符，并提供安全的 sandbox 策略与输入护栏。
