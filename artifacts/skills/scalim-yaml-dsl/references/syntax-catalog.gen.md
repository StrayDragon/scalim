# Scalim YAML DSL Syntax Catalog

此文档由 `scripts/gen-agent-skill.py` 自动生成.
为节省 token,主体数据以 TOON 格式给出;使用时建议直接复制下方 code block.

```toon
generated_by: scripts/gen-agent-skill.py
sources:
  demand_schema: src/scalim/dsl/by_yaml/schema/demand.gen.json
  workflow_schema: src/scalim/dsl/by_yaml/schema/workflow.gen.json
  canonical_example: references/generated/example-full/ecommerce_report.gen.yaml
  validator: src/scalim/dsl/by_yaml/config_parsing/validator.py
builtin_callables[1	]: ^workflow/book_sheet_rows
demand_top_fields[21	]{name	required}:
  name	false
  imports	false
  $import	false
  _templates	false
  description	false
  batch_size	false
  retry	false
  main_source	false
  sources	false
  fields	false
  relations	false
  guardrails	false
  resources	false
  outputs_defaults	false
  outputs	false
  validate_unique_field_names	false
  failure_policy	false
  include_full_error_message	false
  meta	false
  audit	false
  observability	false
demand_definitions[34	]: book	book_budget	book_export_xlsx	book_write_defaults	field	guardrails	guardrails_compute	guardrails_loader	guardrails_relations	loader_retry	logging	main_source	memory_opt	observability	output_aggregate	output_container	output_extra_sheet	output_target	output_to	output_write	outputs_defaults	outputs_defaults_to	performance	performance_report	performance_thresholds	relation	relation_report	relations	resources	row_gap	source	source_field_inline	trace	viz
openspec_requirement_map[15	]{slug	path	purpose	requirements}:
  yaml-dsl-schema	openspec/specs/yaml-dsl-schema/spec.md	通过 dataclass 元数据生成 YAML DSL JSON Schema(`demand.gen.json`),作为校验与编辑器提示的唯一来源.	"enums and defaults MUST be sourced from schema_dsl SSOT\nschema 元数据生成与 hover 指引\nschema 为 `value_cast` 增加 `decimal` 枚举值\noutputs 字段 hover 指引明确可选与 overrides 推荐写法\n`header_fields_output_by` default is `name`\nschema exposes a switch for unique effective field display names\nschema hover 提供常见错误与迁移提示\nschema hover documents `$keys/$rows` directive nodes under `params`\n`params` hover documents `{$runtime: <name>}` and preload params behavior\n顶层 schema 字段(guardrails)\nobservability.logging 支持 renderer/preset 字段\nschema hover 说明 loader 引用支持相对模块语法\n字段声明位置与 compute 约束\nschema documents `extract` as current-row-relative field extraction\nschema removes legacy `field` and provides migration guidance\nrelation steps-only 约束\noutput.fields 解析与 schema 指引\n字段 ID 唯一性与解析规则\n派生字段支持 call_by Schema\nschema meta key 参考文档与推荐写法\nschema meta 中 schema dict 不得吞掉 desc/md\nschema 明确 batch_size 的 null-or-int 语义\nretry 字段纳入 JSON Schema 与 hover 指引\n`_templates.retry.*` 受 schema 校验但 `_templates` 其它内容保持 freeform\nschema 说明源代码级 `normalize` 及其执行顺序\nschema keeps `normalize` out of `main_source`\n`outputs.*.fields` 支持 YAML alias 条目\nalias identity 失败时允许唯一内容匹配\nschema 允许 `outputs.*.fields` 包含 object 条目\nschema 覆盖 `outputs.*.container.path` 的 `{$init_var: <name>}` 语法\nschema MUST support `{$init_var: <name>}` for book export paths\ndemand schema MUST reject legacy output container types and shapes (legacy workbook container surface, pathless `csv`)\nworkflow schema MUST reject legacy workflow IO fields"
  demand-dsl	openspec/specs/demand-dsl/spec.md	实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.	"顶层结构与 IR 转换规则\nunknown fields 诊断提供 suggestions(CLI/库一致)\nLoader 引用解析与 allowlist\nSource/Bind 结构与 keys 分片参数\nloader params templates support `{$runtime: <name>}` directives\n字段/关系表达式默认行为\nmain_source 批次排序配置\n顶层 batch_size 语义统一且可显式禁用分批\nbatch_size 校验在不同入口语义一致\nYAML DSL 增加 loader retry 配置入口\n`_templates.retry` 用于复用通用策略\n`should_retry` 引用解析与 allowlist\n`normalize` is allowed on `sources.*` and rejected on `main_source`\naggregate derived fields MUST support dependency-driven evaluation (DAG)\naggregate fields MUST support safe compute derived fields (`compute`)"
  yaml-dsl-workflow	openspec/specs/yaml-dsl-workflow/spec.md	提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).	"workflow public guidance MUST use curated stable entrypoints\nWorkflow YAML declares runs and options\nRuns execute demand YAML via existing compilation pipeline\nWorkflow enforces failure_policy\nmax_concurrency limits parallel runs deterministically\nworkflow nodes declare explicit DAG deps via `depends_on`\nworkflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)\nctx guardrails MUST be configurable via `workflow.options.ctx`\ndemand nodes MUST publish a minimal default ctx summary\n`$ctx` directives are resolved during compile-on-ready materialization\nfailure propagation cancels downstream nodes deterministically\nworkflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)\nworkflow entrypoints MUST be importable under Python 3.6\nworkflow emits workflow-level events and injects attribution for demand events\nmax_concurrency>1 requires thread-safe or stateless components\nworkflow YAML MUST use `workflow.resources.books` and MUST reject the legacy workflow write authoring surface"
  yaml-dsl-books-resources	openspec/specs/yaml-dsl-books-resources/spec.md	"定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs_defaults.to.book` / `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义."	"demand/workflow YAML MUST support `resources.books` as the unified Excel IO resource surface\n`books.kind=xlsx_file` MUST define file export semantics and path resolution base\n`books.kind=xlsx_memory` MUST define in-memory budget guards and optional export_xlsx\ndemand MUST bind outputs to books via `outputs_defaults.to.book` and `outputs[*].to`\nstandalone demand MUST fail-fast when a referenced book resource is missing\nworkflow MUST merge books from demand/workflow with deterministic precedence and strict contracts\nbooks MUST support default write behavior and per-output overrides for append vs sheet semantics\nExcel exports MUST escape formula-like strings by default (opt-out via allow_formulas)\ndownstream demands MUST be able to load xlsx_memory book sheet rows via a built-in loader\n`.xlsx` outputs MUST use books binding; legacy workbook container surface MUST be rejected (BREAKING)"
  yaml-dsl-output-overrides	openspec/specs/yaml-dsl-output-overrides/spec.md	"为下游“UI 动态选字段/动态输出”场景提供单一标准做法: demand YAML 保持可复用(通常不声明 `outputs`),调用侧在 `run/compile` 时通过与 YAML 同形的 `overrides.outputs` 显式指定输出。"	"by_yaml runtime MUST accept YAML-shaped `overrides.outputs`\n`overrides.outputs` MUST take precedence over YAML `outputs`\n`overrides.outputs` MUST compile through the same outputs pipeline\nby_yaml runtime MUST accept IO-only overrides for `resources.books` and `outputs_defaults`"
  source-relations	openspec/specs/source-relations/spec.md	使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义.	"steps 结构与 relation 解析/推断规则\nlookup_key 与 lookup_cast/诊断\nref loader params are expressed by target-source params templates\n`$rows` preserves rows barrier semantics for relations\npreload_forever sources reject `$keys/$rows` directives\nlegacy `to_bind` is rejected with a copy-pastable migration hint\n批次内 LoadRef 复用与分片语义\nref loader 依赖信号驱动稳定排序\n关联诊断基于样本值并支持复合键对比\n关联路径与比较输出可读且稳定\nrelation `from` MAY reference pre-relation derived fields on main_source side"
  field-compute	openspec/specs/field-compute/spec.md	定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略.	"字段值 value_cast\ncompute 识别/校验/安全约束\ncompute 表达式允许使用 `Decimal(...)` 构造器\n依赖推导规则与无依赖拒绝\n派生字段执行与错误处理\ncompute 表达式预编译并复用执行\ncompute 编译缓存有上限(有界 LRU)\ncompute failures MUST NOT log raw expressions by default\ncompute audit callback MUST support redaction\ncompile cache operations MUST be safe under concurrent access\ncall_by 派生字段函数调用\ncall_by 上下文引用\ncompute sandbox rejection MUST include an actionable `call_by` migration hint"
  source-cache	openspec/specs/source-cache/spec.md	支持 cache_mode=preload_forever 的数据源在 pipeline 启动前预加载,结果写入 ExecutionRuntime.preloaded_cache 并在关联加载时复用;计划元数据记录已缓存的数据源.	"预加载缓存模式\n关联加载优先命中缓存\n计划元数据记录缓存源\npreload cache stores normalized source results\n`preloaded_cache` concurrency boundary and key space MUST be explicit\n`PreloadCache` signature guardrail MUST be available (opt-in)\nloader SHOULD be idempotent when concurrent / repeated loads are possible"
  workflow-cache-pool	openspec/specs/workflow-cache-pool/spec.md	提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件确保“复用正确且可诊断”.	"workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)\nworkflow provides a cache pool with signature-based keys\ncache pool defines an explicit conflict policy\ncache pool supports lifecycle management and auto-release\ncache pool refcount MUST be derived from Workflow IR when available\ncache pool enforces budgets with a clear policy\ncache pool eviction MUST NOT evict in-flight (loading) entries\ncache pool MUST be observable via workflow-level events"
  workflow-observability-bridge	openspec/specs/workflow-observability-bridge/spec.md	定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约,使 demand 事件可稳定归因到 workflow 节点,并提供最小的 workflow-level 编排事件.	"workflow attributes demand events for stable DAG correlation\nworkflow provides workflow-level observability events\nworkflow preserves demand hooks/observers semantics\nworkflow event catalog is extensible for cache/resources"
  runtime-pruning	openspec/specs/runtime-pruning/spec.md	PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.	"依赖剪枝与计划元数据\nYAML 转换阶段按 output.fields 剪枝字段定义\n运行时字段保留与释放策略"
  loader-retry-policy	openspec/specs/loader-retry-policy/spec.md	TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.	"Loader retry policy 配置模型与默认值\nshould_retry 回调契约\nRetry runner 语义(次数/耗时/退避)\n全局策略与 per-loader 覆盖的解析\niterable/generator 的重试边界"
  runtime-guardrails	openspec/specs/runtime-guardrails/spec.md	定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录.	"Guardrails 配置与默认行为\nquiet 模式违规记录\nLoader 结果结构护栏\nRowLike 字段提取语义(无歧义优先级)\n关键字段缺失护栏\n字段 extractor/value_cast/transform 异常护栏\n关联 null_key/type_error 阈值护栏\ncompute 异常护栏\nGuardrailViolation payload 包含稳定的 guardrail 元字段\nquiet 模式下的 guardrail once_key 去重约定"
  performance-observability	openspec/specs/performance-observability/spec.md	PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.	"性能指标采集与结构化输出\nduration 统计使用单调时钟\n资源采样与报告输出\nObservability DSL 配置与独立开关\nRelationObserver 统计与报告\nadaptive 调度决策可观测性\nconsole reports in observability presets MUST follow dependency-free-console-reports\nchanging console formatting MUST NOT change metrics semantics"
  output-mode-api	openspec/specs/output-mode-api/spec.md	"定义运行时输出语义为“显式 sink 驱动”: 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理."	"输出是否保留内存数据由 sink 表达\n无输出时避免构造返回列表\n允许 tee 同时写文件与显式 sink\ntotal_rows 为稳定元数据\n成功路径 sink.close 失败必须使 run 失败\n异常路径 close 不得覆盖原异常\n异常路径 best-effort 关闭 sink"
entries[59	]{id	scope	key	schema_path	required	ref	type	desc	enum	default	const	examples	constraints}:
  1	demand.field	name	properties.name	false	null	string	需求配置名称. - 必填, 用于标识当前配置	null	null	null	"[\"order_report\"]"	null
  2	demand.field	imports	properties.imports	false	null	object	"片段文件导入别名映射. - key: alias - value: 片段文件路径(字符串) - V2 支持相对路径 fragments(解析基准: 当前 YAML 文件所在目录): - `./x.yaml` / `x.yaml` - `x/y.yaml`(子目录) - `../x.yaml`(父目录) - 支持(编辑器侧放宽,运行时校验为准): - alias 路径: `@/x.yaml`, `COMMON:/x.yaml`(需 `scalim.yaml` 显式配置) - 内置 preset: `scalim://yaml-dsl/presets/common.yaml`(仅本地白名单) - 禁止(以运行时为准): 绝对路径/非 `scalim://` 的 `URI scheme`/Windows 盘符/反斜杠分隔符等"	null	null	null	null	additionalProperties=string
  3	demand.field	$import	properties.$import	false	null	string | array	"$import 引用. - string: `<alias>(.<segment>)*` - list: 按顺序合并,后者覆盖前者,最终再被本地覆盖 - 仅支持 mapping 片段 - V1 仅支持同级文件导入(见顶层 `imports`)"	null	null	null	"[\"common.sources\",[\"common.sources\",\"other.sources\"]]"	oneOf=2
  4	demand.field	_templates	properties._templates	false	null	object	YAML anchor 模板集合. - 仅用于 YAML 复用(anchors) - 常用于 `fields` / `relations` / `retry`	null	null	null	null	additionalProperties=true
  5	demand.field	description	properties.description	false	null	string	配置描述(可选).	null	null	null	null	null
  6	demand.field	batch_size	properties.batch_size	false	null	null | integer	批处理大小. - 未声明时使用默认值 - `null` 表示禁用分批(单批执行) - `>=1` 的整数表示固定分批大小	null	1000	null	"[null,1000]"	oneOf=2
  7	demand.field	retry	properties.retry	false	null	null	"Loader retry 策略. - 默认关闭: `enabled: false` - 启用后会对 loader 调用的瞬态错误做有限重试 - 需要提供 `should_retry` 回调(安全引用),用于决定是否重试 - 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5"	null	null	null	null	allOf=1
  8	demand.field	main_source	properties.main_source	false	null	null	"主数据源配置. - 必填: `source_id`, `loader` - `source_id` 不能出现在 `sources` 中 - `fields` 仅允许源字段(禁止 `compute`) - `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)"	null	null	null	null	allOf=1
  9	demand.field	sources	properties.sources	false	null	object	"数据源配置映射, key 为 `source_id`. - 每个 source 必填: `loader`, `key` - 不允许包含 `main_source.source_id` - `fields` 仅允许源字段(禁止 `compute`)"	null	null	null	null	minProperties=0; additionalProperties=ref #/definitions/source
  10	demand.field	fields	properties.fields	false	null	object	字段配置映射(仅用于派生字段). - 必须包含 `compute` 或 `call_by` - 不能与源字段同名(避免 source/derived 重名) - 支持 YAML anchor 复用	null	null	null	null	additionalProperties=ref #/definitions/field
  11	demand.field	relations	properties.relations	false	null	object	"命名关联关系映射(steps 模板). - 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用 - string ref: `relation: <relation_id>` 引用 `relations.<relation_id>` - alias 复用: `relation: *<anchor>` (YAML anchor) - steps 必须是等值关联链, 参考 `relation.steps`"	null	null	null	null	additionalProperties=ref #/definitions/relation
  12	demand.field	guardrails	properties.guardrails	false	null	null	运行时护栏配置. - 默认关闭 - 用于控制 loader/relations/compute 等运行期护栏策略	null	null	null	null	allOf=1
  13	demand.field	resources	properties.resources	false	null	null	"可选:IO 资源声明. - 当前稳定入口: `resources.books`"	null	null	null	null	allOf=1
  14	demand.field	outputs_defaults	properties.outputs_defaults	false	null	null	"可选:输出默认 IO 绑定. - 例如 `outputs_defaults.to.book`"	null	null	null	null	allOf=1
  15	demand.field	outputs	properties.outputs	false	null	array	"输出目标列表(有序; 可选). - 顶层 `outputs` 可省略,用于保持 demand YAML 可复用(通常仅承载需求本体) - 需要运行时动态指定输出(字段/路径/sheet/header 策略)时,推荐在 Python 调用侧使用与 YAML 同形的 `overrides.outputs` - 通过 `where` 分发到不同 sheet - 通过 `aggregate` 声明派生汇总输出 - 通过 `from` 复用字段集合与容器配置 - 不再支持旧写法: 顶层 `output:`"	null	null	null	"[[{\"fields\":[\"order_id\",\"user_id\"],\"name\":\"detail\",\"to\":{\"sheet\":\"明细\"}}]]"	minItems=0; items=ref #/definitions/output_target
  16	demand.field	validate_unique_field_names	properties.validate_unique_field_names	false	null	boolean	"预检查: 字段有效展示名(`effective display name`)全局唯一. - 默认启用: 未声明时等价 `true` - 有效展示名定义: - 若 `field.name` 非空: 使用 `name` - 否则回退为 `field_id` - 仅当 `effective outputs` 使用 `container.include_header: true`(显式或默认) 且 `container.header_fields_output_by: name` 时触发 - 显式设置为 `false` 可关闭该检查(不推荐长期使用)"	null	true	null	"[true,false]"	null
  17	demand.field	failure_policy	properties.failure_policy	false	null	string	"多输出失败策略. - `all_fail`: 任一目标失败即失败 - `primary_only`: 非主输出失败将被禁用但不阻断主输出"	all_fail|primary_only	all_fail	null	"[\"all_fail\"]"	null
  18	demand.field	include_full_error_message	properties.include_full_error_message	false	null	boolean	包含完整错误信息(可能包含敏感信息;默认 false).	null	false	null	"[false]"	null
  19	demand.field	meta	properties.meta	false	null	boolean | ref #/definitions/output_extra_sheet	"可选:启用 meta sheet. - `true` 表示启用并使用默认配置 - 对象形式可覆盖 sheet 名称与 workbook 路径"	null	null	null	"[true,{\"sheet\":\"__meta__\"}]"	oneOf=2
  20	demand.field	audit	properties.audit	false	null	boolean | ref #/definitions/output_extra_sheet	"可选:启用 audit sheet. - `true` 表示启用并使用默认配置 - 对象形式可覆盖 sheet 名称与 workbook 路径"	null	null	null	"[true,{\"sheet\":\"__audit__\"}]"	oneOf=2
  21	demand.field	observability	properties.observability	false	null	null	可观测性配置. 包含 `logging`、`performance`、`relations`、`viz`、`trace`、`row_gap` 与 `memory_opt` 子配置.	null	null	null	null	allOf=1
  22	demand.definition	book	definitions.book	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2; allOf=2
  23	demand.definition	book_budget	definitions.book_budget	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  24	demand.definition	book_export_xlsx	definitions.book_export_xlsx	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  25	demand.definition	book_write_defaults	definitions.book_write_defaults	false	null	object	null	null	null	null	null	additionalProperties=false
  26	demand.definition	field	definitions.field	false	null	object	null	null	null	null	null	additionalProperties=true; allOf=1
  27	demand.definition	guardrails	definitions.guardrails	false	null	object	null	null	null	null	null	additionalProperties=false
  28	demand.definition	guardrails_compute	definitions.guardrails_compute	false	null	object	null	null	null	null	null	additionalProperties=false
  29	demand.definition	guardrails_loader	definitions.guardrails_loader	false	null	object	null	null	null	null	null	additionalProperties=false
  30	demand.definition	guardrails_relations	definitions.guardrails_relations	false	null	object	null	null	null	null	null	additionalProperties=false
  31	demand.definition	loader_retry	definitions.loader_retry	false	null	object	null	null	null	null	null	additionalProperties=false
  32	demand.definition	logging	definitions.logging	false	null	object	null	null	null	null	null	additionalProperties=false
  33	demand.definition	main_source	definitions.main_source	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  34	demand.definition	memory_opt	definitions.memory_opt	false	null	object	null	null	null	null	null	additionalProperties=false
  35	demand.definition	observability	definitions.observability	false	null	object	null	null	null	null	null	additionalProperties=false
  36	demand.definition	output_aggregate	definitions.output_aggregate	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  37	demand.definition	output_container	definitions.output_container	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  38	demand.definition	output_extra_sheet	definitions.output_extra_sheet	false	null	object	null	null	null	null	null	additionalProperties=false
  39	demand.definition	output_target	definitions.output_target	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  40	demand.definition	output_to	definitions.output_to	false	null	object	null	null	null	null	null	additionalProperties=false
  41	demand.definition	output_write	definitions.output_write	false	null	object	null	null	null	null	null	additionalProperties=false
  42	demand.definition	outputs_defaults	definitions.outputs_defaults	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  43	demand.definition	outputs_defaults_to	definitions.outputs_defaults_to	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  44	demand.definition	performance	definitions.performance	false	null	object	null	null	null	null	null	additionalProperties=false
  45	demand.definition	performance_report	definitions.performance_report	false	null	object	null	null	null	null	null	additionalProperties=false
  46	demand.definition	performance_thresholds	definitions.performance_thresholds	false	null	object	null	null	null	null	null	additionalProperties=false
  47	demand.definition	relation	definitions.relation	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  48	demand.definition	relation_report	definitions.relation_report	false	null	object	null	null	null	null	null	additionalProperties=false
  49	demand.definition	relations	definitions.relations	false	null	object	null	null	null	null	null	additionalProperties=false
  50	demand.definition	resources	definitions.resources	false	null	object	null	null	null	null	null	additionalProperties=false
  51	demand.definition	row_gap	definitions.row_gap	false	null	object	null	null	null	null	null	additionalProperties=false
  52	demand.definition	source	definitions.source	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  53	demand.definition	source_field_inline	definitions.source_field_inline	false	null	object	null	null	null	null	null	allOf=2
  54	demand.definition	trace	definitions.trace	false	null	object	null	null	null	null	null	additionalProperties=false
  55	demand.definition	viz	definitions.viz	false	null	object	null	null	null	null	null	additionalProperties=false
  56	workflow	workflow	properties.workflow	true	null	object	null	null	null	null	null	additionalProperties=false
  57	workflow	"workflow.runs[*]"	properties.workflow.properties.runs.items	false	null	object	null	null	null	null	null	additionalProperties=false
  58	workflow	workflow.options	properties.workflow.properties.options	false	null	object	null	null	null	null	null	additionalProperties=false
  59	workflow	workflow.resources	properties.workflow.properties.resources	false	null	null	"workflow-scope shared IO resources. - stable surface: `workflow.resources.books`"	null	"{}"	null	null	allOf=1
properties[191	]{entry_id	name	required	summary}:
  4	retry	false	object
  9	$import	false	string | array, oneOf(2)
  11	$import	false	string | array, oneOf(2)
  22	$import	false	string | array, oneOf(2)
  22	allow_formulas	false	boolean
  22	budget	false	allOf(1)
  22	export_xlsx	false	allOf(1)
  22	kind	false	string, enum xlsx_file, xlsx_memory
  22	path	false	string | object, oneOf(2)
  22	write_defaults	false	allOf(1)
  22	write_lock	false	boolean
  23	$import	false	string | array, oneOf(2)
  23	max_sheets	false	integer
  23	max_total_cells	false	integer
  24	$import	false	string | array, oneOf(2)
  24	allow_formulas	false	boolean
  24	path	false	string | object, oneOf(2)
  24	write_lock	false	boolean
  25	$import	false	string | array, oneOf(2)
  25	align_by	false	string, enum field_id, header
  25	header_policy	false	string, enum once, always, never
  25	mode	false	string, enum sheet, append
  25	on_conflict	false	string, enum error, overwrite, skip
  25	on_mismatch	false	string, enum error, warn, skip
  26	name	false	string
  26	$import	false	string | array, oneOf(2)
  26	call_by	false	string
  26	compute	false	string
  26	extract	false	string
  26	relation	false	string | object, oneOf(2)
  26	source	false	string
  26	value_cast	false	string, enum auto, int, str, decimal
  27	$import	false	string | array, oneOf(2)
  27	relations	false	ref #/definitions/guardrails_relations
  27	compute	false	ref #/definitions/guardrails_compute
  27	enabled	false	boolean
  27	loader	false	ref #/definitions/guardrails_loader
  27	mode	false	string, enum quiet, fast_fail
  28	$import	false	string | array, oneOf(2)
  28	on_error	false	string, enum quiet, fast_fail
  29	$import	false	string | array, oneOf(2)
  29	on_transform_error	false	string, enum quiet, fast_fail
  29	required_fields	false	array, items string | object, anyOf(2)
  29	validate_result	false	boolean
  30	$import	false	string | array, oneOf(2)
  30	null_key_max_rate	false	关联 null_key 最大比例(0.0-1.0;未设置则不启用)
  30	type_error_max_rate	false	关联 type_error 最大比例(0.0-1.0;未设置则不启用)
  31	$import	false	string | array, oneOf(2)
  31	backoff	false	string, enum fixed, exponential
  31	base_delay_seconds	false	基础等待时间(秒)
  31	enabled	false	boolean
  31	jitter	false	boolean
  31	max_attempts	false	integer
  31	max_delay_seconds	false	最大单次等待时间(秒)
  31	max_elapsed_seconds	false	最大累计耗时(秒,包含 sleep)
  31	should_retry	false	string
  32	$import	false	string | array, oneOf(2)
  32	enabled	false	boolean
  32	renderer	false	string, enum pretty, logger
  33	$import	false	string | array, oneOf(2)
  33	retry	false	allOf(1)
  33	fields	false	object, properties $import
  33	loader	false	string
  33	order_by	false	array, items string
  33	params	false	object, properties $import
  33	source_id	false	string
  34	$import	false	string | array, oneOf(2)
  34	auto_report	false	boolean
  34	enabled	false	boolean
  34	max_fields	false	integer
  35	$import	false	string | array, oneOf(2)
  35	relations	false	allOf(1)
  35	logging	false	allOf(1)
  35	memory_opt	false	allOf(1)
  35	performance	false	allOf(1)
  35	row_gap	false	allOf(1)
  35	trace	false	allOf(1)
  35	viz	false	allOf(1)
  36	$import	false	string | array, oneOf(2)
  36	fields	false	object
  36	distinct_on_overflow	false	string, enum error, truncate
  36	group_by	false	array, items string | object | array, anyOf(3)
  36	max_distinct	false	integer
  36	max_groups	false	integer
  37	$import	false	string | array, oneOf(2)
  37	encoding	false	string
  37	header_fields_output_by	false	string, enum field_id, name
  37	include_header	false	boolean
  37	path	false	string | object, oneOf(2)
  37	streaming	false	boolean
  37	type	false	string, enum csv
  38	$import	false	string | array, oneOf(2)
  38	allow_formulas	false	boolean
  38	path	false	string
  38	sheet	false	string
  38	write_lock	false	boolean
  39	name	false	string
  39	$import	false	string | array, oneOf(2)
  39	fields	false	array, items string | object | array, anyOf(3)
  39	aggregate	false	allOf(1)
  39	container	false	allOf(1)
  39	from	false	string
  39	to	false	allOf(1)
  39	where	false	string
  39	write	false	allOf(1)
  40	$import	false	string | array, oneOf(2)
  40	book	false	string
  40	sheet	false	string
  41	$import	false	string | array, oneOf(2)
  41	align_by	false	string, enum field_id, header
  41	header_policy	false	string, enum once, always, never
  41	mode	false	string, enum sheet, append
  41	on_conflict	false	string, enum error, overwrite, skip
  41	on_mismatch	false	string, enum error, warn, skip
  42	$import	false	string | array, oneOf(2)
  42	to	false	allOf(1)
  43	$import	false	string | array, oneOf(2)
  43	book	false	string
  44	$import	false	string | array, oneOf(2)
  44	enabled	false	boolean
  44	metrics	false	array, items enum duration, memory, cpu
  44	report	false	ref #/definitions/performance_report
  44	sampling_interval	false	integer
  44	thresholds	false	ref #/definitions/performance_thresholds
  45	$import	false	string | array, oneOf(2)
  45	format	false	string, enum console, json, csv, none
  45	include_details	false	boolean
  45	output	false	string
  46	$import	false	string | array, oneOf(2)
  46	batch_duration_warn	false	批次耗时告警阈值(秒)
  46	memory_increase_warn	false	内存增长告警阈值(MB)
  47	$import	false	string | array, oneOf(2)
  47	steps	false	array, items object, properties from, lookup_cast, to
  48	$import	false	string | array, oneOf(2)
  48	format	false	string, enum console, json, none
  48	output	false	string
  49	$import	false	string | array, oneOf(2)
  49	enabled	false	boolean
  49	log_type_mismatch	false	boolean
  49	max_samples	false	integer
  49	report	false	ref #/definitions/relation_report
  49	sampling_rate	false	采样率(0.0-1.0)
  50	$import	false	string | array, oneOf(2)
  50	books	false	object, properties $import
  51	$import	false	string | array, oneOf(2)
  51	data_loader_names	false	array, items string
  51	enabled	false	boolean
  51	primary_loader_name	false	string
  51	sample_limit	false	integer
  52	$import	false	string | array, oneOf(2)
  52	retry	false	allOf(1)
  52	fields	false	object, properties $import
  52	cache_mode	false	string, enum none, preload_forever
  52	key	false	string | array, oneOf(2)
  52	loader	false	string
  52	lookup_cast	false	object, properties name, sep
  52	lookup_chunk_size	false	integer | null, oneOf(2)
  52	normalize	false	object, properties fields, call_by, key_field, kind, on_conflict, on_empty, on_missing, steps, allOf(1)
  52	params	false	object, properties $import
  53	name	false	string
  53	$import	false	string | array, oneOf(2)
  53	extract	false	string
  53	relation	false	string | object, oneOf(2)
  53	source	false	string
  53	value_cast	false	string, enum auto, int, str, decimal
  54	$import	false	string | array, oneOf(2)
  54	enabled	false	boolean
  55	$import	false	string | array, oneOf(2)
  55	append	false	boolean
  55	enabled	false	boolean
  55	env	false	string
  55	output_dir	false	string
  55	output_path	false	string
  55	payload_policy	false	string, enum none, summary, sample, full
  55	run_name	false	string
  55	sample_size	false	integer
  55	snapshot_path	false	string
  55	trace_enabled	false	boolean
  55	use_default_output_dir	false	boolean
  56	resources	false	allOf(1)
  56	options	false	object, properties failure_policy, cache_pool, ctx, max_concurrency
  56	runs	true	array, items object, properties demand, depends_on, id, init_vars, main_rows_from
  57	demand	true	string
  57	depends_on	false	array, items string
  57	id	true	string
  57	init_vars	false	object | null, oneOf(2)
  57	main_rows_from	false	object | null, oneOf(2)
  58	failure_policy	false	string, enum all_fail, primary_only
  58	cache_pool	false	object | null, oneOf(2)
  58	ctx	false	object | null, oneOf(2)
  58	max_concurrency	false	integer
workflow_key_paths[10	]: workflow.runs	"workflow.runs[*].id"	"workflow.runs[*].demand"	"workflow.runs[*].depends_on"	"workflow.runs[*].init_vars"	workflow.options	workflow.options.ctx	workflow.options.cache_pool	workflow.resources	workflow.resources.books
workflow_validation[2	]: "Repo schema-only: uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>"	"LSP header: # yaml-language-server: $schema=.../workflow.gen.json OR # $schema: .../workflow.gen.json (use yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>)"
```
