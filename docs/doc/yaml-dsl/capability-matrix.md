# YAML DSL → IR 能力矩阵

??? note "适用读者"
    - 使用 YAML DSL 的高级使用方:想知道“某个能力能否用 YAML 表达、会编译成什么、缺口在哪里”
    - 项目贡献者:评估哪些能力应进入 YAML 的稳定 authoring surface,哪些应保留为 Python-only

??? note "维护提示"
    - 本页是“能力边界/映射表”,当新增 YAML key、调整编译链路或扩展 IR/执行请求时,应同步更新
    - 代码入口:
      - 静态前端(不 import/不解析引用): `src/scalim/dsl/yaml_dsl/compiler_frontend/compiler.py` (`compile_demand_frontend*`)
      - 编译编排(run/compile): `src/scalim/dsl/yaml_dsl/runtime/compiler.py` (`compile`/`compile_ir`/`build_request`)
      - 运行时链接(RuntimeBindings): `src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py` (`resolve_runtime_bindings`)
      - 编译产物: `src/scalim/dsl/yaml_dsl/runtime/contracts.py` (`Compilation`)
      - IR: `src/scalim/spec/ir/` (例如 `src/scalim/spec/ir/demand.py`, `src/scalim/spec/ir/fields.py`, `src/scalim/spec/ir/sources.py`)
      - 运行时绑定契约: `src/scalim/execution/runtime_bindings.py` (`RuntimeBindings`)

本仓库的 YAML DSL 编译后会同时产出三层对象:

1) `DemandConfig` (schema + 语义校验后的配置对象)
2) `DemandIr` (规划/执行核心使用的 IR)
3) `ExecutionRequest` (输出、可观测性、并行模式等运行时请求)

因此下表的“编译到”列可能指向 IR,也可能指向 `ExecutionRequest`(这类能力不属于 IR 本体,但属于可执行请求的一部分)。

补充: `DemandIr`/`ExecutionPlan` 只保存纯数据(例如 `CallableRefIr`/表达式文本),不保存任何 `Python` 可调用对象.
执行阶段需要的函数对象由“运行时链接”阶段解析/编译后注入到 `ExecutionRequest.runtime_bindings`(`RuntimeBindings`)。

## 1) Demand YAML:顶层/导入/模板

| YAML key | 编译到(主要影响) | 限制/边界 | 替代方案 |
|---|---|---|---|
| `name` | `DemandConfig.name` → `DemandIr.name` | 仅标识用途 | - |
| `description` | `DemandConfig.description` | 当前不进入 IR/执行(用于文档/阅读) | - |
| `batch_size`（已迁出） | `ExecutionRequest.batch_size` | YAML 主线已移除(属于 runtime policy boundary);`validate/compile` 会 fail-fast | 用 `scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(batch_size=...)))` 配置 |
| `_templates` | 仅作为 YAML anchors 容器(不直接编译) | 只用于 YAML 复用;不会被运行时读取 | 使用 `&anchor/*alias` 复用 `retry/fields/relations/...` |
| `imports` | 编译期展开(片段导入) | 仅支持相对 `.yaml/.yml` 文件路径或 `scalim://<preset_id>`;默认相对入口 YAML 目录解析且受 `allow-roots` 限制(可用 CLI `--allowed-yaml-root` 或 `scalim.yaml yaml_dsl.import_roots` 扩展) | 仅靠 YAML anchors 复用(单文件)或显式复制片段 |
| `$import` | 编译期展开(在 mapping 内引用 imports alias) | 仅在“文件路径入口”可用;纯文本入口无法解析文件; **scope 仅限稳定 authoring surfaces**(`main_source/sources/fields/relations/resources`),不允许顶层 `(root)` 与 `outputs.*`/workflow/runtime policy/output extras | 使用 YAML anchors/merge(单文件)或 workflow/Python 拼装 |

## 2) Demand YAML:数据源(main_source/sources)

| YAML key | 编译到(主要影响) | 限制/边界 | 替代方案 |
|---|---|---|---|
| `main_source.source_id` | `DemandIr.main_source.source_id` | 必填;不可与 `sources` key 冲突 | - |
| `main_source.loader` | `DemandIr.main_source.loader_ref` / `RuntimeBindings.main_source_loaders[source_id]` | 静态前端不 import;在“运行时链接”阶段做 allowlist 校验并解析引用(安全边界) | 用 `allowed_modules/allowed_functions` 放行 |
| `main_source.params` | `DemandIr.main_source.params` | 仅允许静态值 + `{$init_var: <name>}`;禁止 `$keys/$rows` | 把动态输入放 `init_vars` 里,并在调用 `run/compile` 时传入 |
| `main_source.retry`（已迁出） | `ExecutionRequest.loader_retry` | YAML 主线已移除(属于 runtime policy boundary);`validate/compile` 会 fail-fast | 用 `scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(loader_retry=...)))` 配置 |
| `main_source.order_by` | `MainSourceIr.order_by` | 仅批次内写入顺序;每项支持 `-field` 表示 desc | 若需要更复杂排序,在 loader 内排序 |
| `main_source.fields.*` | `FieldIr` (source=main) | 仅源字段;禁止 `compute/call_by` | 复杂派生逻辑放 `fields.*`(derived) |
| `sources.*.loader` | `SourceIr.loader_spec.callable_ref` / `RuntimeBindings.source_loaders[source_id]` | 静态前端不 import;在“运行时链接”阶段做 allowlist 校验并解析引用(安全边界) | - |
| `sources.*.key` | `SourceIr.key` (`KeyIr.key`) | 支持单键或复合键(tuple/list) | - |
| `sources.*.lookup_cast` | `SourceIr.key.cast` | 仅提供预置 cast(见 schema choices) | 更复杂归一化用 `normalize.call_by` 或 loader 内处理 |
| `sources.*.lookup_chunk_size` | `SourceIr.lookup_chunk_size` | 仅 keys 模式有效;省略/`0`/`None`=不分片(延迟通常最优);过小会线性放大 loader 调用次数;**不是并行开关** | 仅在下游有 payload/IN 上限时设置,并取最大安全值;片间并行见 Python `parallelize_lookup_chunks`（[0.10.0](../releases/0.10.0.md)） |
| `sources.*.normalize` | `SourceIr.normalize` (`SourceNormalizeIr`) | 仅提供受控 kind + 可选 `call_by` 扩展点 | 若需要任意 reshape,放到 loader 中处理 |
| `sources.*.cache_mode` | `SourceIr.cache_mode` | 目前仅 `none/preload_forever` | 更细粒度缓存策略需 Python 层扩展 |
| `sources.*.retry`（已迁出） | `ExecutionRequest.loader_retry` | YAML 主线已移除(属于 runtime policy boundary);`validate/compile` 会 fail-fast | 用 `scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(loader_retry=...)))` 配置 |
| `sources.*.params` | `SourceIr.bind` (由 params template 推导) | legacy `bind/to_bind` 已移除;用 `$keys/$rows` 指令节点表达 | 需要特殊调用协议时,用自定义 loader 或 Python-only `BindingIr` |
| `sources.*.fields.*` | `FieldIr` (source=that source) | 仅源字段;禁止 `compute/call_by` | 复杂派生逻辑放 `fields.*`(derived) |

## 3) Demand YAML:字段(fields)与关联(relations)

| YAML key | 编译到(主要影响) | 限制/边界 | 替代方案 |
|---|---|---|---|
| `fields.*` | `DerivedFieldIr` | 必须 `compute` 或 `call_by`;依赖自动提取 | 复杂逻辑用 `call_by` |
| `fields.*.compute` | `DerivedFieldIr.compute_expr` / `RuntimeBindings.derived_calculators[field_id]` | 禁止 import/任意执行;表达式能力受限(运行时链接阶段编译为安全函数) | 用 `call_by` 引用 Python 函数 |
| `fields.*.call_by` | `DerivedFieldIr.call_by` / `RuntimeBindings.derived_calculators[field_id]` | 受 allowlist 限制;签名/依赖由解析器约束(运行时链接阶段解析引用) | 将函数放到受控模块并加入 allowlist |
| `*.fields.*.extract` | `FieldIr.extract_expr/extract_segments` | 表达式是“路径提取”;不支持 list index 语义 | 需要复杂提取时在 loader 中生成扁平字段 |
| `*.fields.*.value_cast` | `FieldIr.transform` | 仅预置 cast | 复杂转换用 derived field |
| `*.fields.*.relation` | `FieldIr.lookup_steps`(解析结果) | 只支持等值关联链(steps);路径必须从 main_source 可达 | 在 `relations` 中沉淀命名链路并用 string ref 复用 |
| `relations.*` | 间接影响 `FieldIr.lookup_steps` | relation 本身不进入 IR;作为“链路模板”供字段引用 | 需要完全自定义 lookup 逻辑时,用 Python-only IR 构建 |
| `relations.*.steps[].lookup_cast` | `LookupStepIr.lookup_cast` | 仅预置 cast | 同上 |

## 4) Demand YAML:输出(outputs/meta/audit)

| YAML key | 编译到(主要影响) | 限制/边界 | 替代方案 |
|---|---|---|---|
| `outputs[]` | `ExecutionRequest.output_composition` (`OutputCompositionSpec`) | `RunOverrides.outputs` 可整体替换(仅承诺 `name/to/fields` 最小子集;不支持 `where/from/aggregate`) | 运行期动态输出: `run(..., options=DemandRunOptions(..., outputs=DemandRunOutputOptions(overrides=RunOverrides(outputs=(OutputOverride(...),)))))` 或 `RunOverrides.<factory>(...)` |
| `outputs.*.to` / `outputs.*.write` | `OutputTargetSpec.output` (`OutputSpec`) | `to` 必须二选一: `to.file` 或 `to.book`; `write` 仅承载 output-local header 行为(`include_header/header_fields_output_by`),workbook 写入策略以 Python `ResourcesPolicy`/`BookWritePolicy` 为 SSOT | DSL `run` 不再支持自定义 `sink`;如需捕获行数据用 `DemandRunOutputOptions(capture=CaptureRows())`;如需完全自定义 sink 走 execution 层入口 |
| `outputs.*.container`（已移除） | - | 已移除;`validate/compile` 会 `fail-fast` | CSV: `resources.files` + `outputs.*.to.file`; Excel: `resources.books` + `outputs.*.to.book/to.sheet` |
| `resources.books.*.write_defaults`（已迁出） | - | 已迁出 YAML;`validate/compile` fail-fast | `DemandRunOptions`/`WorkflowRunOptions.resources_policy` → `BookWritePolicy`(StrEnum) |
| `resources.books.*.budget` / `xlsx.budget` / 旧 `xlsx_memory.budget`（已移除） | - | 能力已删除;`validate/compile` 残留即 fail-fast；内存风险交宿主 cgroup/OOM/作业配额 | 删除该字段；**不要**再找 `BookBudgetPolicy`（已移除，见 upgrade `2026-07-28-remove-book-budget-policy`） |
| `resources.files.<id>.path` | `OutputSpec.path` | 支持静态 string 或 `{$init_var: <name>}`(对象节点;仅编译期解析一次;不做子串插值);缺失 init_var fail-fast;相对路径相对 **YAML 文件目录** | 用 Python 侧 `init_vars` 注入、`BookResourceOverride`/`FileResourceOverride` 覆盖,或改用绝对路径 |
| `outputs.*.fields` | `ExportLayout.field_ids` | 支持 `field_id` string + YAML alias(object/list)并 flatten | 若 alias identity 丢失且内容匹配歧义,改用 string `field_id` |
| `outputs.*.where` | `OutputTargetSpec.predicate` | 安全表达式;依赖字段静态提取注入 required fields | 复杂分发逻辑放到 loader/derived field 里生成路由字段 |
| `outputs.*.aggregate` | `DerivedOutputTargetSpec.derived`(group_by) | YAML 暴露 `group_by` + `fields`(metric / rank / `compute` / `call_by`);旧 `metrics` 与基数护栏字段(`max_groups` 等)已移除并 fail-fast | `dedup_by` / 两阶段派生装配**已移除**（见 upgrade `2026-07-28-remove-dedup-and-two-stage-derived`）；去重用 loader/上游，两阶段用 workflow 两段 demand |
| `outputs.*.from` | 输出继承(字段/容器) | 不继承 where/aggregate | - |
| `meta` / `audit`（已迁出） | `OutputCompositionSpec.meta_sheet/audit_sheet` | 不再属于 YAML 主线;通过 `RunOverrides.output_extras` 配置(需要 workbook 上下文;workflow 模式不支持显式 path) | `run(..., options=DemandRunOptions(..., outputs=DemandRunOutputOptions(overrides=RunOverrides(output_extras=OutputExtrasOverride(meta=True, audit=True)))))` |
| `failure_policy`（已迁出） | `OutputCompositionSpec.failure_policy` | `all_fail/primary_only` | `run(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(demand_failure_policy=\"all_fail\"|\"primary_only\")))` |
| `include_full_error_message`（已迁出） | `OutputCompositionSpec.include_full_error_message` | 可能包含敏感信息;默认 false | `run(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(demand_diagnostics=DemandDiagnosticsPolicy(include_full_error_message=True))))` |

## 5) Demand YAML:护栏(guardrails)

| YAML key | 编译到(主要影响) | 限制/边界 | 替代方案 |
|---|---|---|---|
| `guardrails`（已迁出） | `ExecutionRequest.guardrails` (`GuardrailsPolicy`) | YAML 主线已移除(属于 runtime policy boundary);`validate/compile` 会 fail-fast | 用 `scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(guardrails=...)))` 配置 |

## 6) 当前“不在 YAML 里”的常用能力(需要 Python/CLI 参数)

| 能力 | 对应对象 | 为什么不在 YAML | 推荐用法 |
|---|---|---|---|
| allowlist | `SecurePythonReferenceResolver` | 安全边界(运行环境/组织策略差异大) | `scalim.dsl.yaml_dsl.run(..., options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=..., allowed_functions=...)))` 或 CLI flags |
| `init_vars` | `DemandRunTemplateOptions.init_vars` | 运行时输入,不应写死在共享 YAML | `run(..., options=DemandRunOptions(..., template=DemandRunTemplateOptions(init_vars={...})))` |
| 并行模式/并发数 | `ExecutionRequest.parallel_mode/max_workers` | 与环境/资源相关,容易导致不可复现 | `run(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(parallel_mode=\"seq|adaptive\", max_workers=...)))` |
| lookup chunk 并行（0.10） | `DemandRunRuntimeOptions.parallelize_lookup_chunks` / `max_chunk_workers` | 运行期 opt-in；`lookup_chunk_size` 仍只表示分片大小 | `DemandRunRuntimeOptions(parallel_mode=\"adaptive\", parallelize_lookup_chunks=True)`；详见 [0.10.0 重点特性](../releases/0.10.0.md) / [§3.6](../architecture/parallel-modes.md) |
| 自定义 sink | `ExecutionRequest.sink` | sink 往往是运行环境能力(文件系统/内存/对象存储) | DSL `run` 不再接受 `sink`;捕获行数据用 `DemandRunOutputOptions(capture=CaptureRows())`;完全自定义 sink 走 execution 层入口 |
| 完全自定义 outputs | `ExecutionRequest.output_composition` | 组合输出属于执行装配层,复杂度高 | 使用 execution 层入口 `scalim.execution.run_ir(...)` 自行构造 `ExecutionRequest(output_composition=...)` |
| 自定义 hooks/observers | `ExecutionRequest.components` | 运行期组件需要 Python 对象 | `run(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(components=[Observer(), Hook()])))` |
| 内置可观测 presets + Viz | `ExecutionRequest.components` + `ExecutionRequest.observability.viz_config` | 可观测性属于 runtime integration surface,不作为 YAML authoring surface | `run(..., options=DemandRunOptions(..., runtime=DemandRunRuntimeOptions(components=[PerformanceObserver(), RelationObserver(), ...]), outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(...)))))` |
| book 写入策略 | `ResourcesPolicy` / `BookWritePolicy` | runtime policy boundary(环境/安全/性能差异大);YAML `write_defaults` 再写会 fail-fast | `run`/`run_workflow(..., options=... resources_policy=ResourcesPolicy(books={...}))`;迁移见 skill upgrade `2026-07-12-book-write-policy-python-ssot`。book cell/sheet **budget 已移除**（`2026-07-28-remove-book-budget-policy`）；YAML/`RunOverrides` 残留 `budget` 仍 fail-fast，请删除 |

## 7) IR 已存在但 YAML 未暴露的典型缺口(候选清单)

以下能力在 IR/执行层存在,但目前不属于 YAML 的稳定 authoring surface:

- `export_profile`/字段展示: `DemandIr.export_profile` + `FieldPresentationIr` (Excel number_format/列宽等)。
- 主键/主字段语义: `FieldIr.is_primary` 目前在 YAML 编译链路中固定为 `False`。
- source 级 fk/bindings: `SourceIr.fk_fields`/`SourceIr.bindings` 目前不暴露(仅保留 `bind` 由 params 推导)。
- 更多 sink/output 类型: YAML 当前稳定 surface 仅覆盖 `resources.files(csv_file)` 与 `resources.books`（统一 `xlsx` 可选 `path`；旧 `xlsx_file`/`xlsx_memory` 已硬删）。

## 8) 建议(用于下一轮评估)

1) **先把“缺口”分类**: 哪些是“执行环境参数”(更适合 CLI/Python options),哪些是“需求本体”(更适合 YAML/IR)。
2) **优先补最小可迁移面**: 例如把 `FieldPresentationIr` 先收敛成一小组 YAML 可表达的 `presentation` 子集(Excel number_format/width/align),其余仍 Python-only。
3) **复杂装配保持 Python-only,但做稳定扩展点**: 例如为 outputs 引入受控 `extensions` 或把更多 derived targets 以 llmanspec changes 逐步落地到 YAML,避免一次性暴露完整 IR。
4) **把 “Not in YAML” 的运行期参数在 CLI/教程里显式化**: 例如 `parallel_mode/max_workers/init_vars` 的推荐默认值与可复现策略。
