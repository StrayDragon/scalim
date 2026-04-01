<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `openspec/specs/*/spec.md`
-->
# OpenSpec 索引(生成)

说明:
- 本页仅做“索引与链接”,不把 `openspec/specs/**` 作为站点页面.
- 规范本体以仓库文件为准,请通过代码链接打开.

## Specs

### `agent-skill-export`
- Title: agent-skill-export Specification
- Source: [spec.md](#code=openspec/specs/agent-skill-export/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `scalim-yaml-dsl` skill 自动生成器的职责边界,确保自动化只负责受控参考产物,同时保证输出可校验、可重建、不会覆盖手工维护的 skill 本体.

### `agent-skill-workflow-writes-docs`
- Title: agent-skill-workflow-writes-docs Specification
- Source: [spec.md](#code=openspec/specs/agent-skill-workflow-writes-docs/spec.md)
- Summary: 定义并约束 `scalim-yaml-dsl` skill 的 workflow YAML 语法索引生成规则,确保生成物的关键 key paths 与 canonical workflow schema 一致,避免文档漂移误导作者与工具链.

### `benchmarking`
- Title: benchmarking Specification
- Source: [spec.md](#code=openspec/specs/benchmarking/spec.md)
- Summary: **状态: ✅ 已实现** 定义基准测试入口与依赖约束,覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析.

### `dataclassesx-vendor`
- Title: dataclassesx-vendor Specification
- Source: [spec.md](#code=openspec/specs/dataclassesx-vendor/spec.md)
- Summary: **状态: ✅ 已实现** 为 `src/scalim/` 提供一个可 vendors 化、可审计的 dataclasses 能力入口,在保持 Python 3.6 运行时兼容的同时避免依赖外部 `dataclasses` backport,并避免包内绝对导入在多份包共存时混入错误实现。

### `demand-dsl`
- Title: demand-dsl Specification
- Source: [spec.md](#code=openspec/specs/demand-dsl/spec.md)
- Summary: **状态: ✅ 已实现** 实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.

### `dense-batch-context`
- Title: dense-batch-context Specification
- Source: [spec.md](#code=openspec/specs/dense-batch-context/spec.md)
- Summary: TBD - created by archiving change c60-performance-optimization-abc. Update Purpose after archive.

### `dependency-free-console-reports`
- Title: dependency-free-console-reports Specification
- Source: [spec.md](#code=openspec/specs/dependency-free-console-reports/spec.md)
- Summary: TBD - created by archiving change c2-remove-literich. Update Purpose after archive.

### `derived-outputs`
- Title: derived-outputs Specification
- Source: [spec.md](#code=openspec/specs/derived-outputs/spec.md)
- Summary: **状态: ⚠️ 实验性** 支持在同一次运行中基于详情行流生成派生输出(增量聚合 + finalize 阶段输出),并定义 IR/Python-only 配置入口、资源护栏与 `adaptive` 并发边界.

### `deterministic-ordering`
- Title: deterministic-ordering Specification
- Source: [spec.md](#code=openspec/specs/deterministic-ordering/spec.md)
- Summary: **状态: ✅ 已实现** 定义 PROJECT_NAME 的稳定顺序最小契约,用于保证 planning/执行在相同输入下可复现,并避免 `PYTHONHASHSEED` 等非确定性因素影响结果. 本 spec 覆盖执行计划构建顺序、拓扑排序输出的 tie-break 规则、以及 keys 绑定列表的稳定顺序要求.

### `doc-governance`
- Title: doc-governance Specification
- Source: [spec.md](#code=openspec/specs/doc-governance/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库内文档的分层、生成边界(`*.gen.*` + `AUTOGEN` 注入区块)、统一生成入口与漂移门禁,以降低维护成本并防止“手工修改生成物/区块”导致的不一致.

### `docs-site`
- Title: docs-site Specification
- Source: [spec.md](#code=openspec/specs/docs-site/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库内文档站点的范围与组织规则:使用 Zensical(兼容 MkDocs 的配置格式)构建站点,以 `docs/doc/` 作为唯一文档真源,并避免将 `openspec/specs/**`、`_REPORT/**` 等规范/审计内容纳入站点.

### `dsl-runtime-structure`
- Title: dsl-runtime-structure Specification
- Source: [spec.md](#code=openspec/specs/dsl-runtime-structure/spec.md)
- Summary: **状态: ✅ 已实现** 定义 by_yaml runtime 作为 DSL adapter/编译器的边界与对外入口,并明确 YAML `output`/`observability` 在编译期映射为 DSL-agnostic 运行请求对象的规则.

### `error-taxonomy`
- Title: error-taxonomy Specification
- Source: [spec.md](#code=openspec/specs/error-taxonomy/spec.md)
- Summary: **状态: ✅ 已实现** 为 `scalim` 建立统一的异常体系规范:以 `ScalimError(Exception)` 作为唯一根,并在其下按域拆分子类;对用户可感知错误以异常类型/显式字段作为稳定契约;同时约束错误事件的最小输出与敏感信息治理,并提供可执行的测试断言口径.

### `execution-structure`
- Title: execution-structure Specification
- Source: [spec.md](#code=openspec/specs/execution-structure/spec.md)
- Summary: **状态: ✅ 已实现** 定义 execution 层的模块拆分与入口契约,并明确统一 IR 编排入口(如 `run_ir`)的边界,确保执行编排对 DSL 配置解耦且行为在重构后保持兼容.

### `explicit-extension-points`
- Title: explicit-extension-points Specification
- Source: [spec.md](#code=openspec/specs/explicit-extension-points/spec.md)
- Summary: **状态: ✅ 已实现** 定义 PROJECT_NAME 内部扩展点的显式注入与编译式分发模型,减少模块级“魔法注入”与事件热路径反射,提升类型友好性、可维护性与性能稳定性.

### `field-compute`
- Title: field-compute Specification
- Source: [spec.md](#code=openspec/specs/field-compute/spec.md)
- Summary: **状态: ✅ 已实现** 定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略.

### `flow-visualization`
- Title: flow-visualization Specification
- Source: [spec.md](#code=openspec/specs/flow-visualization/spec.md)
- Summary: **状态: ✅ 已实现** - VizGraphSnapshot + VizEventStream 可视化机制已实现 提供执行过程的可视化输出:VizGraphSnapshot 从 ExecutionPlan 生成 XYFlow 兼容的 nodes/edges 结构用于依赖图展示;VizEventStream 将 Hook 事件映射为可视化事件流支持离线回放.

### `framework-logging`
- Title: framework-logging Specification
- Source: [spec.md](#code=openspec/specs/framework-logging/spec.md)
- Summary: **状态: ✅ 已实现** 为框架内部日志建立统一的 Python 标准库 `logging` 使用约定,以保证默认静默、命名空间稳定、输出前缀一致,并提供可扩展的诊断字段与 context 绑定机制。

### `generated-artifacts-manifest`
- Title: generated-artifacts-manifest Specification
- Source: [spec.md](#code=openspec/specs/generated-artifacts-manifest/spec.md)
- Summary: 统一“生成物 / 注入区块”的约定与门禁,避免引入额外的 manifest SSOT 与重复维护成本.

### `hooks-events`
- Title: hooks-events Specification
- Source: [spec.md](#code=openspec/specs/hooks-events/spec.md)
- Summary: TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.

### `hooks-observability-structure`
- Title: hooks-observability-structure Specification
- Source: [spec.md](#code=openspec/specs/hooks-observability-structure/spec.md)
- Summary: **状态: ✅ 已实现** 定义 Hook/Observer/事件体系的统一边界:事件契约、分发路径、组件装配与高频路径性能语义.

### `instrumentation-hub`
- Title: instrumentation-hub Specification
- Source: [spec.md](#code=openspec/specs/instrumentation-hub/spec.md)
- Summary: TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.

### `ir-structure`
- Title: ir-structure Specification
- Source: [spec.md](#code=openspec/specs/ir-structure/spec.md)
- Summary: **状态: ✅ 已实现** 定义 IR 层的纯数据边界与依赖约束,确保 spec/ir 不依赖执行与规划层,便于稳定复用、演进与测试.

### `key-normalization`
- Title: key-normalization Specification
- Source: [spec.md](#code=openspec/specs/key-normalization/spec.md)
- Summary: `key_normalization` 提供一个运行期可控的“稳定字符串口径”键匹配策略,用于解决 relations/derived outputs 中 `1` 与 `"1"` 等跨来源类型不一致导致的 miss/分组拆分问题. 该能力为 `EXPERIMENTAL`,默认关闭(`raw`).

### `legacy-vendors-sync`
- Title: legacy-vendors-sync Specification
- Source: [spec.md](#code=openspec/specs/legacy-vendors-sync/spec.md)
- Summary: **状态: ✅ 已实现** 为下游采用 `vendors/libs/` 导入链路的旧工程提供一个可审计、可重复的同步入口,用于将本仓库的 `src/scalim/` vendors 化后镜像到目标 `<vendors/libs>/scalim/`。默认仅预览(dry-run),并在显式确认时执行实际同步。

### `loader-retry-policy`
- Title: loader-retry-policy Specification
- Source: [spec.md](#code=openspec/specs/loader-retry-policy/spec.md)
- Summary: TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.

### `marimo-demo-big-data-report-chapters`
- Title: marimo-demo-big-data-report-chapters Specification
- Source: [spec.md](#code=openspec/specs/marimo-demo-big-data-report-chapters/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `demo_big_data_report` 主线示例在 `notebooks/marimo/` 下的章节化组织要求:以 `demo_main.py` 作为 hub,每个 SSOT chapter 对应一本 Marimo notebook,并与 headless runner/pytest 同源对拍.

### `marimo-example-public-api-suite`
- Title: marimo-example-public-api-suite Specification
- Source: [spec.md](#code=openspec/specs/marimo-example-public-api-suite/spec.md)
- Summary: TBD - created by archiving change c16-demo-big-data-report-yaml-mainline. Update Purpose after archive.

### `marimo-notebooks-examples-suite`
- Title: marimo-notebooks-examples-suite Specification
- Source: [spec.md](#code=openspec/specs/marimo-notebooks-examples-suite/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库内 `notebooks/marimo/` 的示例/教学套件治理边界:Marimo notebooks 作为唯一交互载体,headless runner/pytest 作为确定性回归入口,并要求执行真相来源位于 notebooks(同源复用).

### `misc`
- Title: misc Specification
- Source: [spec.md](#code=openspec/specs/misc/spec.md)
- Summary: **状态: ✅ 已实现** 为“重构分析类文档”提供统一的规范入口与最低要求,确保依赖分析、边界说明、任务拆分、验证口径和约束声明一致,以便在不改动代码的前提下形成可复核的决策依据.

### `module-organization`
- Title: module-organization Specification
- Source: [spec.md](#code=openspec/specs/module-organization/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `src/IMPL_ROOT/` 的模块边界、入口最小化与兼容约束,避免将内部实现路径误用为公共 API,并保持 Python 3.6 运行时可用性.

### `no-external-callback-under-lock`
- Title: no-external-callback-under-lock Specification
- Source: [spec.md](#code=openspec/specs/no-external-callback-under-lock/spec.md)
- Summary: 为执行层的并发安全定义护栏：任何可能触发用户回调（hooks/observers）或外部回调的操作不得在内部互斥锁临界区内执行，避免重入/锁顺序反转导致的死锁。

### `observer-concurrency-contract`
- Title: observer-concurrency-contract Specification
- Source: [spec.md](#code=openspec/specs/observer-concurrency-contract/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow 并发执行（例如 `max_concurrency>1`）时 observers/hooks/components 的默认并发语义,确保在不要求 observer 实现方线程安全的前提下仍具备可解释、可复现的事件回放顺序,并保持 `no-external-callback-under-lock` 护栏不被破坏.

### `ordered-unique-ssot`
- Title: ordered-unique-ssot Specification
- Source: [spec.md](#code=openspec/specs/ordered-unique-ssot/spec.md)
- Summary: TBD - created by archiving change c40-ordered-unique-ssot. Update Purpose after archive.

### `output-aggregate-producer-keys-ssot`
- Title: output-aggregate-producer-keys-ssot Specification
- Source: [spec.md](#code=openspec/specs/output-aggregate-producer-keys-ssot/spec.md)
- Summary: TBD - created by archiving change c45-output-aggregate-producer-keys-ssot. Update Purpose after archive.

### `output-composition`
- Title: output-composition Specification
- Source: [spec.md](#code=openspec/specs/output-composition/spec.md)
- Summary: **状态: ✅ 已实现** 支持单次运行的多输出目标组合(多文件或同一容器多逻辑输出),并定义容器命名冲突策略与输出失败策略(`failure_policy`).

### `output-mode-api`
- Title: output-mode-api Specification
- Source: [spec.md](#code=openspec/specs/output-mode-api/spec.md)
- Summary: **状态: ✅ 已实现** 定义运行时输出语义为“显式 sink 驱动”: 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理.

### `outputs-parser-staged-design`
- Title: outputs-parser-staged-design Specification
- Source: [spec.md](#code=openspec/specs/outputs-parser-staged-design/spec.md)
- Summary: TBD - created by archiving change c50-outputs-parser-split. Update Purpose after archive.

### `overlap-optimization`
- Title: overlap-optimization Specification
- Source: [spec.md](#code=openspec/specs/overlap-optimization/spec.md)
- Summary: **状态: 📋 待实现** - 当前方案为暂不处理,跨批次复用缓存待实现 当前实现不提供跨批次的关联结果复用,除 preload_forever 外每个批次独立加载并在执行时重算;该状态与 ExecutionRuntime 仅持有预加载缓存的行为一致.

### `package-identity`
- Title: package-identity Specification
- Source: [spec.md](#code=openspec/specs/package-identity/spec.md)
- Summary: TBD - created by archiving change projectlib-rename-uv-lib-migration. Update Purpose after archive.

### `package-metadata`
- Title: package-metadata Specification
- Source: [spec.md](#code=openspec/specs/package-metadata/spec.md)
- Summary: **状态: ✅ 已实现** 为 `scalim` 提供一套轻量、稳定、Python 3.6 兼容的运行时版本号入口（`__version__`），用于排查与集成，并与 `pyproject.toml` 的 `project.version` 保持一致.

### `parallel-execution`
- Title: parallel-execution Specification
- Source: [spec.md](#code=openspec/specs/parallel-execution/spec.md)
- Summary: **状态: ⚠️ 实验性** 定义执行层对外并发语义 `seq|adaptive`,以及 `adaptive` 下的调度边界、后端选择、结果提交与事件回放契约.

### `perf-regression-guardrails`
- Title: perf-regression-guardrails Specification
- Source: [spec.md](#code=openspec/specs/perf-regression-guardrails/spec.md)
- Summary: TBD - created by archiving change c60-performance-optimization-abc. Update Purpose after archive.

### `performance-observability`
- Title: performance-observability Specification
- Source: [spec.md](#code=openspec/specs/performance-observability/spec.md)
- Summary: **状态: ✅ 已实现** PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.

### `preload-cache-concurrent-load-scenarios`
- Title: preload-cache-concurrent-load-scenarios Specification
- Source: [spec.md](#code=openspec/specs/preload-cache-concurrent-load-scenarios/spec.md)
- Summary: TBD - created by archiving change c70-preload-cache-concurrent-load-scenarios. Update Purpose after archive.

### `preload-cache-inflight-dedupe`
- Title: preload-cache-inflight-dedupe Specification
- Source: [spec.md](#code=openspec/specs/preload-cache-inflight-dedupe/spec.md)
- Summary: TBD - created by archiving change c0-preload-cache-inflight-dedupe. Update Purpose after archive.

### `preload-cache-inflight-wait-diagnostics`
- Title: preload-cache-inflight-wait-diagnostics Specification
- Source: [spec.md](#code=openspec/specs/preload-cache-inflight-wait-diagnostics/spec.md)
- Summary: TBD - created by archiving change c75-preload-cache-inflight-wait-diagnostics. Update Purpose after archive.

### `preload-cache-signature-guardrail`
- Title: preload-cache-signature-guardrail Specification
- Source: [spec.md](#code=openspec/specs/preload-cache-signature-guardrail/spec.md)
- Summary: TBD - created by archiving change c700-preload-cache-signature-guardrail. Update Purpose after archive.

### `prompt-eval-fixture-cli`
- Title: prompt-eval-fixture-cli Specification
- Source: [spec.md](#code=openspec/specs/prompt-eval-fixture-cli/spec.md)
- Summary: **状态: ✅ 已实现** 定义 prompt-eval coding-agent workspace 的 fixture CLI 隔离策略,确保其不覆盖仓库真实 `scalim-cli`,同时保持 workspace 内 `uv run scalim-cli ...` 命令模板可复现,并避免对 PyPI build 依赖/网络造成的 dry-run 波动。

### `prompt-eval-workflow`
- Title: prompt-eval-workflow Specification
- Source: [spec.md](#code=openspec/specs/prompt-eval-workflow/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库级 prompt 评测/回归工作流的最低要求,用于守护关键 skill/指令文本的质量与文档治理边界规则,并提供稳定的本地运行入口与 CI 产物。

### `public-api-manifest`
- Title: public-api-manifest Specification
- Source: [spec.md](#code=openspec/specs/public-api-manifest/spec.md)
- Summary: **状态: ✅ 已实现** 定义 public API 边界治理规则,并在不引入“符号级硬 manifest SSOT”的前提下,确保: - 稳定入口清晰(约定 + 文档) - `__all__` 显式治理(避免隐式暴露内部实现) - 用户材料不得引用内部导入路径(避免把内部实现写进教程/示例/skills)

### `public-api-surface-governance`
- Title: public-api-surface-governance Specification
- Source: [spec.md](#code=openspec/specs/public-api-surface-governance/spec.md)
- Summary: **状态: ✅ 已实现** 定义稳定公开入口的编目规则与回归门禁,避免内部实现路径在文档/skills/examples/tests 中被误固化为事实公共 API.

### `runtime-guardrails`
- Title: runtime-guardrails Specification
- Source: [spec.md](#code=openspec/specs/runtime-guardrails/spec.md)
- Summary: **状态: ✅ 已实现** 定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录.

### `runtime-pruning`
- Title: runtime-pruning Specification
- Source: [spec.md](#code=openspec/specs/runtime-pruning/spec.md)
- Summary: **状态: ✅ 已实现** PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.

### `sink-fastpath`
- Title: sink-fastpath Specification
- Source: [spec.md](#code=openspec/specs/sink-fastpath/spec.md)
- Summary: TBD - created by archiving change c60-performance-optimization-abc. Update Purpose after archive.

### `sinks-contracts`
- Title: sinks-contracts Specification
- Source: [spec.md](#code=openspec/specs/sinks-contracts/spec.md)
- Summary: **状态: ✅ 已实现** 定义 sink 接口稳定性与可选依赖提示规范,确保内建与外部 sink 的长期兼容、可诊断性与一致行为.

### `skill-docs-write-to-cleanup`
- Title: skill-docs-write-to-cleanup Specification
- Source: [spec.md](#code=openspec/specs/skill-docs-write-to-cleanup/spec.md)
- Summary: 定义并约束 `scalim-yaml-dsl` skill 与相关 OpenSpec 文档对 workflow 写入语义的表述口径,确保作者不会被已移除的旧写入字段误导,并以 `workflow.resources.books` + demand outputs 的 `to/write` 绑定作为唯一可用的 authoring surface(SSOT).

### `source-cache`
- Title: source-cache Specification
- Source: [spec.md](#code=openspec/specs/source-cache/spec.md)
- Summary: **状态: ✅ 已实现** 支持 cache_mode=preload_forever 的数据源在 pipeline 启动前预加载,结果写入 ExecutionRuntime.preloaded_cache 并在关联加载时复用;计划元数据记录已缓存的数据源.

### `source-relations`
- Title: source-relations Specification
- Source: [spec.md](#code=openspec/specs/source-relations/spec.md)
- Summary: **状态: ✅ 已实现** 使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义.

### `streaming-output`
- Title: streaming-output Specification
- Source: [spec.md](#code=openspec/specs/streaming-output/spec.md)
- Summary: **状态: ✅ 已实现** 支持 IRowSink 与 IColumnSink 的流式写入路径,定义 main source 行流、分批与 `row_id` 规则,并约束行式路径“行就绪即写出 + rows 绑定 release 屏障”语义.

### `testing-quality`
- Title: testing-quality Specification
- Source: [spec.md](#code=openspec/specs/testing-quality/spec.md)
- Summary: **状态: ✅ 已实现** 定义测试分类、覆盖率门槛与 demo 对拍验证的最低要求,明确默认测试范围与质量门禁,确保持续集成结果稳定可复现.

### `tests-domain-suites`
- Title: tests-domain-suites Specification
- Source: [spec.md](#code=openspec/specs/tests-domain-suites/spec.md)
- Summary: TBD - created by archiving change c2-tests-domain-suites. Update Purpose after archive.

### `workflow-cache-pool`
- Title: workflow-cache-pool Specification
- Source: [spec.md](#code=openspec/specs/workflow-cache-pool/spec.md)
- Summary: **状态: ✅ 已实现** 提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件确保“复用正确且可诊断”.

### `workflow-intermediate-store`
- Title: workflow-intermediate-store Specification
- Source: [spec.md](#code=openspec/specs/workflow-intermediate-store/spec.md)
- Summary: TBD - created by archiving change c15-workflow-intermediate-store-optimizations. Update Purpose after archive.

### `workflow-ir`
- Title: workflow-ir Specification
- Source: [spec.md](#code=openspec/specs/workflow-ir/spec.md)
- Summary: TBD - created by archiving change c18-workflow-ir-roadmap. Update Purpose after archive.

### `workflow-managed-temp-outputs`
- Title: workflow-managed-temp-outputs Specification
- Source: [spec.md](#code=openspec/specs/workflow-managed-temp-outputs/spec.md)
- Summary: TBD - created by archiving change c50-workflow-managed-temp-outputs. Update Purpose after archive.

### `workflow-observability-bridge`
- Title: workflow-observability-bridge Specification
- Source: [spec.md](#code=openspec/specs/workflow-observability-bridge/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约,使 demand 事件可稳定归因到 workflow 节点,并提供最小的 workflow-level 编排事件.

### `workflow-replay-bundle`
- Title: workflow-replay-bundle Specification
- Source: [spec.md](#code=openspec/specs/workflow-replay-bundle/spec.md)
- Summary: TBD - created by archiving change c10-workflow-viz-linked-replay. Update Purpose after archive.

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
- Summary: TBD - created by archiving change c30-workflow-shared-output-containers. Update Purpose after archive.

### `workflow-sheetbook-resources`
- Title: workflow-sheetbook-resources Specification
- Source: [spec.md](#code=openspec/specs/workflow-sheetbook-resources/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow YAML 的共享 `.xlsx` book 资源(以 `workflow.resources.books` 表达)的迁移约束与运行期契约: 预算护栏、确定性写入、冲突安全、可观测且可原子导出为最终 xlsx,并提供可稳定引用的内置 loader 供下游节点读取 sheet rows.

### `yaml-dsl-agent-guidance`
- Title: yaml-dsl-agent-guidance Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-agent-guidance/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `scalim-yaml-dsl` 手工维护 skill 的任务驱动组织方式,确保 agent 能基于最小入口、明确命令和按需 references 一次完成 YAML 编写、升级、校验、订正与渐进迁移方案设计.

### `yaml-dsl-allowed-paths-policy`
- Title: yaml-dsl-allowed-paths-policy Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-allowed-paths-policy/spec.md)
- Summary: TBD - created by archiving change c25-yaml-path-escape-hardening. Update Purpose after archive.

### `yaml-dsl-allowlist-policy`
- Title: yaml-dsl-allowlist-policy Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-allowlist-policy/spec.md)
- Summary: TBD - created by archiving change c2-allowlist-footgun-hardening. Update Purpose after archive.

### `yaml-dsl-books-resources`
- Title: yaml-dsl-books-resources Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-books-resources/spec.md)
- Summary: 定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义.

### `yaml-dsl-builtin-callables`
- Title: yaml-dsl-builtin-callables Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-builtin-callables/spec.md)
- Summary: 为 `YAML DSL` 中的 loader/call_by/... 等 Python 可调用对象引用点提供一套 **稳定、受控、无需扩大 allowlist** 的内置 callable 引用语法,避免下游依赖 `scalim.*` 内部模块路径。

### `yaml-dsl-cli-validation`
- Title: yaml-dsl-cli-validation Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-cli-validation/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.

### `yaml-dsl-demo-scenarios-suite`
- Title: yaml-dsl-demo-scenarios-suite Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-demo-scenarios-suite/spec.md)
- Summary: TBD - created by archiving change c16-demo-big-data-report-yaml-mainline. Update Purpose after archive.

### `yaml-dsl-docs-skills-autogen-sync`
- Title: yaml-dsl-docs-skills-autogen-sync Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-docs-skills-autogen-sync/spec.md)
- Summary: TBD - created by archiving change c30-yaml-dsl-docs-skills-autogen-sync. Update Purpose after archive.

### `yaml-dsl-file-resources`
- Title: yaml-dsl-file-resources Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-file-resources/spec.md)
- Summary: **状态: ✅ 已实现** 定义 demand/workflow 统一的 `resources.files` 文件输出资源入口,并约束 CSV 输出通过 `outputs[*].to.file` + `outputs[*].write` 绑定,取代 legacy `outputs[*].container`.

### `yaml-dsl-import-aliases-and-presets`
- Title: yaml-dsl-import-aliases-and-presets Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-import-aliases-and-presets/spec.md)
- Summary: TBD - created by archiving change c80-yaml-dsl-import-aliases-and-presets. Update Purpose after archive.

### `yaml-dsl-imports`
- Title: yaml-dsl-imports Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-imports/spec.md)
- Summary: **状态: ✅ 已实现** 为 demand YAML 提供跨文件复用能力: 顶层 `imports` + 任意 mapping 内 `$import`(编译期展开),并在 schema/语义校验前完成展开.

### `yaml-dsl-mainline-principles`
- Title: yaml-dsl-mainline-principles Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-mainline-principles/spec.md)
- Summary: 定义 YAML DSL 的上位主线原则与设计护栏,用于约束后续变更的方向与评审口径: 单主线原地演进、authoring/runtime policy 分离、KV-first、以及 workflow 小而声明式(拒绝 imports expansion)。

### `yaml-dsl-micro-tunes`
- Title: yaml-dsl-micro-tunes Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-micro-tunes/spec.md)
- Summary: TBD - created by archiving change yaml-dsl-micro-tunes. Update Purpose after archive.

### `yaml-dsl-output-overrides`
- Title: yaml-dsl-output-overrides Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-output-overrides/spec.md)
- Summary: **状态: ✅ 已实现** 为下游“UI 动态选字段/动态输出”场景提供单一标准做法: demand YAML 保持可复用(通常不声明 `outputs`),调用侧在 `run/compile` 时通过 typed `RunOverrides` 显式指定输出编排与 IO 覆盖。

### `yaml-dsl-public-tools`
- Title: yaml-dsl-public-tools Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-public-tools/spec.md)
- Summary: 为 `YAML DSL` 的下游集成提供稳定“工具/自省”公开入口,避免下游依赖 by_yaml runtime 的内部实现模块路径。

### `yaml-dsl-render-effective-yaml`
- Title: yaml-dsl-render-effective-yaml Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-render-effective-yaml/spec.md)
- Summary: **状态: ✅ 已实现** 提供用于 review/debug/对拍的**库侧 API**,将“作者写的 demand YAML”渲染为 effective YAML(展开后的单文件等价配置),避免 imports/template 复用在 review 时变成黑盒。

### `yaml-dsl-schema`
- Title: yaml-dsl-schema Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-schema/spec.md)
- Summary: **状态: ✅ 已实现** 通过 dataclass 元数据生成 YAML DSL JSON Schema(`demand.gen.json`),作为校验与编辑器提示的唯一来源.

### `yaml-dsl-unified-loader`
- Title: yaml-dsl-unified-loader Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-unified-loader/spec.md)
- Summary: TBD - created by archiving change c30-yaml-dsl-rigor-ssot. Update Purpose after archive.

### `yaml-dsl-workflow`
- Title: yaml-dsl-workflow Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-workflow/spec.md)
- Summary: **状态: ✅ 已实现** 提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).

### `yaml-dsl-workflow-validate`
- Title: yaml-dsl-workflow-validate Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-workflow-validate/spec.md)
- Summary: TBD - created by archiving change c12-yaml-dsl-workflow-validate-cli. Update Purpose after archive.

### `yaml-field-extract`
- Title: yaml-field-extract Specification
- Source: [spec.md](#code=openspec/specs/yaml-field-extract/spec.md)
- Summary: **状态: ✅ 已实现** 为 YAML DSL 的源字段提供稳定、可维护的字段级取值能力:用 `extract` 从“当前 key 对应的 row value”读取嵌套字段与非字符串 key 字段,以消除仅为拍平/投影而编写 Python wrapper 的必要。

### `yaml-inline-dynamic-params`
- Title: yaml-inline-dynamic-params Specification
- Source: [spec.md](#code=openspec/specs/yaml-inline-dynamic-params/spec.md)
- Summary: **状态: ✅ 已实现** 为 YAML DSL 的 ref loader 参数构造提供“kwargs 模板 + 内联动态节点”的稳定入口:在 `sources.<id>.params` 中用 `$keys/$rows` 指令节点注入运行时上下文,支持任意嵌套位置注入,并保留 rows barrier 与批次内复用语义,以替代 legacy `bind/to_bind` 与 wrapper 方案.

### `yaml-runtime-vars`
- Title: yaml-runtime-vars Specification
- Source: [spec.md](#code=openspec/specs/yaml-runtime-vars/spec.md)
- Summary: **状态: ✅ 已实现** 为 by_yaml runtime 提供编译期的运行期变量注入入口: 调用方通过 `runtime_vars` 注入任意 Python 对象,并在 `main_source.params` / `sources.<id>.params` 的 kwargs 模板中用 `{$runtime: <name>}` 指令节点引用,由 adapter 在编译期解析并透传给 loader.

### `yaml-source-normalize`
- Title: yaml-source-normalize Specification
- Source: [spec.md](#code=openspec/specs/yaml-source-normalize/spec.md)
- Summary: TBD - created by archiving change yaml-source-normalize. Update Purpose after archive.

### `yaml-template-vars-precompile`
- Title: yaml-template-vars-precompile Specification
- Source: [spec.md](#code=openspec/specs/yaml-template-vars-precompile/spec.md)
- Summary: TBD - created by archiving change c5-yaml-template-vars-precompile. Update Purpose after archive.

### `yaml-template-vars-sandbox`
- Title: yaml-template-vars-sandbox Specification
- Source: [spec.md](#code=openspec/specs/yaml-template-vars-sandbox/spec.md)
- Summary: TBD - created by archiving change c20-yaml-template-vars-sandbox. Update Purpose after archive.
