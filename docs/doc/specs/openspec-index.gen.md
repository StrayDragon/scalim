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
- Summary: **状态: ✅ 已实现** 定义 `scalim-yaml-dsl` skill 自动生成器的职责边界,确保自动化只负责受控参考产物与构建清单,同时保证输出可校验、可重建、不会覆盖手工维护的 skill 本体.

### `benchmarking`
- Title: benchmarking Specification
- Source: [spec.md](#code=openspec/specs/benchmarking/spec.md)
- Summary: **状态: ✅ 已实现** 定义基准测试入口与依赖约束,覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析.

### `demand-dsl`
- Title: demand-dsl Specification
- Source: [spec.md](#code=openspec/specs/demand-dsl/spec.md)
- Summary: **状态: ✅ 已实现** 实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.

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

### `loader-retry-policy`
- Title: loader-retry-policy Specification
- Source: [spec.md](#code=openspec/specs/loader-retry-policy/spec.md)
- Summary: TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.

### `marimo-demo-big-data-report-chapters`
- Title: marimo-demo-big-data-report-chapters Specification
- Source: [spec.md](#code=openspec/specs/marimo-demo-big-data-report-chapters/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `demo_big_data_report` 主线示例在 `notebooks/marimo/` 下的章节化组织要求:以 `demo_main.py` 作为 hub,每个 SSOT chapter 对应一本 Marimo notebook,并与 headless runner/pytest 同源对拍.

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

### `output-composition`
- Title: output-composition Specification
- Source: [spec.md](#code=openspec/specs/output-composition/spec.md)
- Summary: **状态: ✅ 已实现** 支持单次运行的多输出目标组合(多文件或同一容器多逻辑输出),并定义容器命名冲突策略与输出失败策略(`failure_policy`).

### `output-mode-api`
- Title: output-mode-api Specification
- Source: [spec.md](#code=openspec/specs/output-mode-api/spec.md)
- Summary: **状态: ✅ 已实现** 定义运行时输出语义为“显式 sink 驱动”: 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理.

### `overlap-optimization`
- Title: overlap-optimization Specification
- Source: [spec.md](#code=openspec/specs/overlap-optimization/spec.md)
- Summary: **状态: 📋 待实现** - 当前方案为暂不处理,跨批次复用缓存待实现 当前实现不提供跨批次的关联结果复用,除 preload_forever 外每个批次独立加载并在执行时重算;该状态与 ExecutionRuntime 仅持有预加载缓存的行为一致.

### `package-identity`
- Title: package-identity Specification
- Source: [spec.md](#code=openspec/specs/package-identity/spec.md)
- Summary: TBD - created by archiving change projectlib-rename-uv-lib-migration. Update Purpose after archive.

### `parallel-execution`
- Title: parallel-execution Specification
- Source: [spec.md](#code=openspec/specs/parallel-execution/spec.md)
- Summary: **状态: ⚠️ 实验性** 定义执行层对外并发语义 `seq|adaptive`,以及 `adaptive` 下的调度边界、后端选择、结果提交与事件回放契约.

### `performance-observability`
- Title: performance-observability Specification
- Source: [spec.md](#code=openspec/specs/performance-observability/spec.md)
- Summary: **状态: ✅ 已实现** PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.

### `prompt-eval-fixture-cli`
- Title: prompt-eval-fixture-cli Specification
- Source: [spec.md](#code=openspec/specs/prompt-eval-fixture-cli/spec.md)
- Summary: **状态: ✅ 已实现** 定义 prompt-eval coding-agent workspace 的 fixture CLI 隔离策略,确保其不覆盖仓库真实 `scalim-cli`,同时保持 workspace 内 `uv run scalim-cli ...` 命令模板可复现,并避免对 PyPI build 依赖/网络造成的 dry-run 波动。

### `prompt-eval-workflow`
- Title: prompt-eval-workflow Specification
- Source: [spec.md](#code=openspec/specs/prompt-eval-workflow/spec.md)
- Summary: **状态: ✅ 已实现** 定义仓库级 prompt 评测/回归工作流的最低要求,用于守护关键 skill/指令文本的质量与文档治理边界规则,并提供稳定的本地运行入口与 CI 产物。

### `runtime-guardrails`
- Title: runtime-guardrails Specification
- Source: [spec.md](#code=openspec/specs/runtime-guardrails/spec.md)
- Summary: **状态: ✅ 已实现** 定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录.

### `runtime-pruning`
- Title: runtime-pruning Specification
- Source: [spec.md](#code=openspec/specs/runtime-pruning/spec.md)
- Summary: **状态: ✅ 已实现** PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.

### `sinks-contracts`
- Title: sinks-contracts Specification
- Source: [spec.md](#code=openspec/specs/sinks-contracts/spec.md)
- Summary: **状态: ✅ 已实现** 定义 sink 接口稳定性与可选依赖提示规范,确保内建与外部 sink 的长期兼容、可诊断性与一致行为.

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

### `workflow-cache-pool`
- Title: workflow-cache-pool Specification
- Source: [spec.md](#code=openspec/specs/workflow-cache-pool/spec.md)
- Summary: **状态: ✅ 已实现** 提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件确保“复用正确且可诊断”.

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

### `workflow-shared-output-containers`
- Title: workflow-shared-output-containers Specification
- Source: [spec.md](#code=openspec/specs/workflow-shared-output-containers/spec.md)
- Summary: TBD - created by archiving change c30-workflow-shared-output-containers. Update Purpose after archive.

### `workflow-sheetbook-resources`
- Title: workflow-sheetbook-resources Specification
- Source: [spec.md](#code=openspec/specs/workflow-sheetbook-resources/spec.md)
- Summary: **状态: ✅ 已实现** 定义 workflow YAML 的 sheetbook 资源(authoring surface)、预算护栏与写入 intent(`write_to.sheetbook_*`)契约,并要求写入行为确定性、冲突安全、可观测且可原子导出为最终 xlsx,同时提供内置 loader 供下游节点读取 sheet rows.

### `yaml-dsl-agent-guidance`
- Title: yaml-dsl-agent-guidance Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-agent-guidance/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `scalim-yaml-dsl` 手工维护 skill 的任务驱动组织方式,确保 agent 能基于最小入口、明确命令和按需 references 一次完成 YAML 编写、升级、校验、订正与渐进迁移方案设计.

### `yaml-dsl-cli-validation`
- Title: yaml-dsl-cli-validation Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-cli-validation/spec.md)
- Summary: **状态: ✅ 已实现** 定义 `PROJECT_CLI_NAME yaml-dsl ...` 的校验分层、严格模式、JSON 输出与诊断输出格式(含源码位置),以确保 CLI 校验结果可用于 IDE 跳转、CI 报告与脚本化消费,并避免与 schema 生成规范耦合.

### `yaml-dsl-editor-core`
- Title: yaml-dsl-editor-core Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-editor-core/spec.md)
- Summary: **状态: ✅ 已实现** 定义 YAML DSL 编辑器的核心能力:文本优先编辑、Visual 双向同步、统一校验模型、roundtrip 稳定性与可选 exact(Pyodide)语义校验.

### `yaml-dsl-imports`
- Title: yaml-dsl-imports Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-imports/spec.md)
- Summary: **状态: ✅ 已实现** 为 demand YAML 提供跨文件复用能力: 顶层 `imports` + 任意 mapping 内 `$import`(编译期展开),并在 schema/语义校验前完成展开.

### `yaml-dsl-micro-tunes`
- Title: yaml-dsl-micro-tunes Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-micro-tunes/spec.md)
- Summary: TBD - created by archiving change yaml-dsl-micro-tunes. Update Purpose after archive.

### `yaml-dsl-schema`
- Title: yaml-dsl-schema Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-schema/spec.md)
- Summary: **状态: ✅ 已实现** 通过 dataclass 元数据生成 YAML DSL JSON Schema(`demand.gen.json`),作为校验与编辑器提示的唯一来源.

### `yaml-dsl-workflow`
- Title: yaml-dsl-workflow Specification
- Source: [spec.md](#code=openspec/specs/yaml-dsl-workflow/spec.md)
- Summary: **状态: ✅ 已实现** 提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).

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
