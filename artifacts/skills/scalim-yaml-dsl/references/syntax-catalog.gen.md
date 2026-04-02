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
demand_top_fields[12	]{name	required}:
  name	true
  imports	false
  _templates	false
  description	false
  main_source	true
  sources	false
  fields	false
  relations	false
  resources	false
  outputs	false
  validate_unique_field_names	false
  include_full_error_message	false
demand_definitions[21	]: book	book_budget	book_export_xlsx	book_write_defaults	field	file	guardrails	guardrails_compute	guardrails_loader	guardrails_relations	loader_retry	main_source	output_aggregate	output_extra_sheet	output_target	output_to	output_write	relation	resources	source	source_field_inline
openspec_requirement_map[15	]{slug	path	purpose	requirements}:
  yaml-dsl-schema	openspec/specs/yaml-dsl-schema/spec.md	通过 dataclass 元数据生成 YAML DSL JSON Schema(`demand.gen.json`),作为校验与编辑器提示的唯一来源.	"enums and defaults MUST be sourced from schema_dsl SSOT\nschema 元数据生成与 hover 指引\ndemand JSON Schema MUST validate source identifiers and reject empty loader/key\nschema 为 `value_cast` 增加 `decimal` 枚举值\noutputs 字段 hover 指引明确可选与 overrides 推荐写法\nschema MUST expose the unified output target surface and reject legacy `container`\ndemand JSON Schema MUST encode composed outputs invariants (streaming=true, detail fields source)\n`header_fields_output_by` default is `name`\nschema exposes a switch for unique effective field display names\nschema hover 提供常见错误与迁移提示\nschema hover documents `$keys/$rows` directive nodes under `params`\n`params` hover documents `{$runtime: <name>}` and preload params behavior\n顶层 schema 字段(guardrails)\nschema hover 说明 loader 引用支持相对模块语法\n字段声明位置与 compute 约束\nschema documents `extract` as current-row-relative field extraction\nschema removes legacy `field` and provides migration guidance\nrelation steps-only 约束\noutput.fields 解析与 schema 指引\n字段 ID 唯一性与解析规则\n派生字段支持 call_by Schema\nschema meta key 参考文档与推荐写法\nschema meta 中 schema dict 不得吞掉 desc/md\nschema 明确 batch_size 的 null-or-int 语义\nretry 字段纳入 JSON Schema 与 hover 指引\ndemand JSON Schema MUST reject empty retry.should_retry when provided\n`_templates.retry.*` 受 schema 校验但 `_templates` 其它内容保持 freeform\nschema 说明源代码级 `normalize` 及其执行顺序\nschema keeps `normalize` out of `main_source`\n`outputs.*.fields` 支持 YAML alias 条目\nalias identity 失败时允许唯一内容匹配\nschema 允许 `outputs.*.fields` 包含 object 条目\nschema MUST support `{$init_var: <name>}` for file resource paths\nschema MUST support `{$init_var: <name>}` for book export paths\ndemand schema MUST reject legacy output container surface and invalid file paths\nworkflow schema MUST reject legacy workflow IO fields"
  demand-dsl	openspec/specs/demand-dsl/spec.md	实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.	"顶层结构与 IR 转换规则\nsource_id and sources keys MUST be valid identifiers and validated fail-fast\nunknown fields 诊断提供 suggestions(CLI/库一致)\nLoader 引用解析与 allowlist\nSource/Bind 结构与 keys 分片参数\nloader params templates support `{$runtime: <name>}` directives\n字段/关系表达式默认行为\nmain_source 批次排序配置\n顶层 batch_size 语义统一且可显式禁用分批\nbatch_size 校验在不同入口语义一致\nYAML DSL 增加 loader retry 配置入口\n`_templates.retry` 用于复用通用策略\n`should_retry` 引用解析与 allowlist\n`normalize` is allowed on `sources.*` and rejected on `main_source`\naggregate derived fields MUST support dependency-driven evaluation (DAG)\naggregate fields MUST support safe compute derived fields (`compute`)"
  yaml-dsl-workflow	openspec/specs/yaml-dsl-workflow/spec.md	提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).	"workflow public guidance MUST use curated stable entrypoints\nWorkflow YAML declares runs and options\nRuns execute demand YAML via existing compilation pipeline\nWorkflow enforces failure_policy\nmax_concurrency limits parallel runs deterministically\nworkflow nodes declare explicit DAG deps via `depends_on`\nworkflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)\nctx guardrails MUST be configurable via `workflow.options.ctx`\ndemand nodes MUST publish a minimal default ctx summary\n`$ctx` directives are resolved during compile-on-ready materialization\nfailure propagation cancels downstream nodes deterministically\nworkflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)\nworkflow entrypoints MUST be importable under Python 3.6\nworkflow emits workflow-level events and injects attribution for demand events\nmax_concurrency>1 requires thread-safe or stateless components\nworkflow YAML MUST use `workflow.resources.books` and MUST reject the legacy workflow write authoring surface\nworkflow.options.resources_wait MUST configure join/wait diagnostics and timeout\nworkflow.options.output_staging MUST configure staging directory and cleanup policy"
  yaml-dsl-books-resources	openspec/specs/yaml-dsl-books-resources/spec.md	定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义.	"demand/workflow YAML MUST support `resources.books` as the unified Excel IO resource surface\n`books.kind=xlsx_file` MUST define file export semantics and path resolution base\n`books.kind=xlsx_memory` MUST define in-memory budget guards and optional export_xlsx\ndemand MUST bind outputs to books via `outputs[*].to.book` and `outputs[*].to.sheet`\nstandalone demand MUST fail-fast when a referenced book resource is missing\nworkflow MUST merge books from demand/workflow with deterministic precedence and strict contracts\nbooks MUST support default write behavior and per-output overrides for append vs sheet semantics\nExcel exports MUST escape formula-like strings by default (opt-out via allow_formulas)\ndownstream demands MUST be able to load xlsx_memory book sheet rows via a built-in loader\n`.xlsx` outputs MUST use books binding; legacy workbook container surface MUST be rejected (BREAKING)"
  yaml-dsl-output-overrides	openspec/specs/yaml-dsl-output-overrides/spec.md	"为下游“UI 动态选字段/动态输出”场景提供单一标准做法: demand YAML 保持可复用(通常不声明 `outputs`),调用侧在 `run/compile` 时通过 typed `RunOverrides` 显式指定输出编排与 IO 覆盖。"	"by_yaml runtime MUST accept typed `RunOverrides.outputs` (dataclasses)\n`RunOverrides` MUST provide factory methods for the common “single-sheet dynamic fields export” scenario\nlegacy YAML-shaped overrides inputs MUST be rejected with actionable migration hints\n`RunOverrides.outputs` MUST take precedence over YAML `outputs`\n`RunOverrides.outputs` MUST compile through the same outputs pipeline\nby_yaml runtime MUST accept IO-only overrides for `resources` and `outputs_defaults`"
  source-relations	openspec/specs/source-relations/spec.md	使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义.	"steps 结构与 relation 解析/推断规则\nlookup_key 与 lookup_cast/诊断\nref loader params are expressed by target-source params templates\n`$rows` preserves rows barrier semantics for relations\npreload_forever sources reject `$keys/$rows` directives\nlegacy `to_bind` is rejected with a copy-pastable migration hint\n批次内 LoadRef 复用与分片语义\nref loader 依赖信号驱动稳定排序\n关联诊断基于样本值并支持复合键对比\n关联路径与比较输出可读且稳定\nrelation `from` MAY reference pre-relation derived fields on main_source side"
  field-compute	openspec/specs/field-compute/spec.md	定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略.	"字段值 value_cast\ncompute 识别/校验/安全约束\ncompute 安全引擎 MUST provide a safe `dec(x)` decimal helper\ncompute 表达式允许使用 `Decimal(...)` 构造器\n依赖推导规则与无依赖拒绝\n派生字段执行与错误处理\ncompute 表达式预编译并复用执行\ncompute 编译缓存有上限(有界 LRU)\ncompute failures MUST NOT log raw expressions by default\ncompute audit callback MUST support redaction\ncompile cache operations MUST be safe under concurrent access\ncall_by 派生字段函数调用\ncall_by 上下文引用\ncompute sandbox rejection MUST include an actionable `call_by` migration hint"
  source-cache	openspec/specs/source-cache/spec.md	支持 cache_mode=preload_forever 的数据源在 pipeline 启动前预加载,结果写入 ExecutionRuntime.preloaded_cache 并在关联加载时复用;计划元数据记录已缓存的数据源.	"预加载缓存模式\n关联加载优先命中缓存\n计划元数据记录缓存源\npreload cache stores normalized source results\n`preloaded_cache` concurrency boundary and key space MUST be explicit\n`PreloadCache` signature guardrail MUST be available (opt-in)\nloader SHOULD be idempotent when concurrent / repeated loads are possible"
  workflow-cache-pool	openspec/specs/workflow-cache-pool/spec.md	提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件确保“复用正确且可诊断”.	"workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)\nworkflow provides a cache pool with signature-based keys\ncache pool defines an explicit conflict policy\ncache pool supports lifecycle management and auto-release\ncache pool refcount MUST be derived from Workflow IR when available\ncache pool enforces budgets with a clear policy\ncache pool eviction MUST NOT evict in-flight (loading) entries\ncache pool MUST be observable via workflow-level events"
  workflow-observability-bridge	openspec/specs/workflow-observability-bridge/spec.md	定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约,使 demand 事件可稳定归因到 workflow 节点,并提供最小的 workflow-level 编排事件.	"workflow attributes demand events for stable DAG correlation\nworkflow provides workflow-level observability events\nworkflow preserves demand hooks/observers semantics\nworkflow event catalog is extensible for cache/resources"
  runtime-pruning	openspec/specs/runtime-pruning/spec.md	PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.	"依赖剪枝与计划元数据\nYAML 转换阶段按 output.fields 剪枝字段定义\n运行时字段保留与释放策略"
  loader-retry-policy	openspec/specs/loader-retry-policy/spec.md	TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.	"Loader retry policy 配置模型与默认值\nshould_retry 回调契约\nRetry runner 语义(次数/耗时/退避)\n全局策略与 per-loader 覆盖的解析\niterable/generator 的重试边界"
  runtime-guardrails	openspec/specs/runtime-guardrails/spec.md	定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录.	"Guardrails 配置与默认行为\nquiet 模式违规记录\nLoader 结果结构护栏\nRowLike 字段提取语义(无歧义优先级)\n关键字段缺失护栏\n字段 extractor/value_cast/transform 异常护栏\n关联 null_key/type_error 阈值护栏\ncompute 异常护栏\nGuardrailViolation payload 包含稳定的 guardrail 元字段\nquiet 模式下的 guardrail once_key 去重约定"
  performance-observability	openspec/specs/performance-observability/spec.md	PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.	"性能指标采集与结构化输出\nduration 统计使用单调时钟\n资源采样与报告输出\nruntime entrypoints 装配与独立开关\nRelationObserver 统计与报告\nadaptive 调度决策可观测性\nconsole reports in observability presets MUST follow dependency-free-console-reports\nchanging console formatting MUST NOT change metrics semantics"
  output-mode-api	openspec/specs/output-mode-api/spec.md	"定义运行时输出语义为“显式 sink 驱动”: 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理."	"输出是否保留内存数据由 sink 表达\n无输出时避免构造返回列表\n允许 tee 同时写文件与显式 sink\ntotal_rows 为稳定元数据\n成功路径 sink.close 失败必须使 run 失败\n异常路径 close 不得覆盖原异常\n异常路径 best-effort 关闭 sink"
entries[37	]{id	scope	key	schema_path	required	ref	type	desc	enum	default	const	examples	constraints}:
  1	demand.field	name	properties.name	true	null	string	需求配置名称. - 必填, 用于标识当前配置	null	null	null	"[\"order_report\"]"	null
  2	demand.field	imports	properties.imports	false	null	object	"片段文件导入别名映射. - key: alias - value: 片段文件路径(字符串) - V2 支持相对路径 fragments(解析基准: 当前 YAML 文件所在目录): - `./x.yaml` / `x.yaml` - `x/y.yaml`(子目录) - `../x.yaml`(父目录) - 支持(编辑器侧放宽,运行时校验为准): - alias 路径: `@/x.yaml`, `COMMON:/x.yaml`(需 `scalim.yaml` 显式配置) - 内置 preset: `scalim://yaml-dsl/presets/common.yaml`(仅本地白名单) - 禁止(以运行时为准): 绝对路径/非 `scalim://` 的 `URI scheme`/Windows 盘符/反斜杠分隔符等"	null	null	null	null	additionalProperties=string
  3	demand.field	_templates	properties._templates	false	null	object	YAML anchor 模板集合. - 仅用于 YAML 复用(anchors) - 常用于 `fields` / `relations`	null	null	null	null	additionalProperties=true
  4	demand.field	description	properties.description	false	null	string	配置描述(可选).	null	null	null	null	null
  5	demand.field	main_source	properties.main_source	true	null	null	"主数据源配置. - 必填: `source_id`, `loader` - `source_id` 不能出现在 `sources` 中 - `fields` 仅允许源字段(禁止 `compute`) - `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)"	null	null	null	null	allOf=1
  6	demand.field	sources	properties.sources	false	null	object	"数据源配置映射, key 为 `source_id`. - 每个 source 必填: `loader`, `key` - 不允许包含 `main_source.source_id` - `fields` 仅允许源字段(禁止 `compute`)"	null	null	null	null	minProperties=0; additionalProperties=ref #/definitions/source
  7	demand.field	fields	properties.fields	false	null	object	字段配置映射(仅用于派生字段). - 必须包含 `compute` 或 `call_by` - 不能与源字段同名(避免 source/derived 重名) - 支持 YAML anchor 复用	null	null	null	null	additionalProperties=ref #/definitions/field
  8	demand.field	relations	properties.relations	false	null	object	"命名关联关系映射(steps 模板). - 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用 - string ref: `relation: <relation_id>` 引用 `relations.<relation_id>` - alias 复用: `relation: *<anchor>` (YAML anchor) - steps 必须是等值关联链, 参考 `relation.steps`"	null	null	null	null	additionalProperties=ref #/definitions/relation
  9	demand.field	resources	properties.resources	false	null	null	"可选:IO 资源声明. - 稳定入口: `resources.books` / `resources.files`"	null	null	null	null	allOf=1
  10	demand.field	outputs	properties.outputs	false	null	array	"输出目标列表(有序; 可选). - 顶层 `outputs` 可省略,用于保持 demand YAML 可复用(通常仅承载需求本体) - 需要运行时动态指定输出(字段/路径/sheet/header 策略)时,推荐在 Python 调用侧使用与 YAML 同形的 `overrides.outputs` - 通过 `where` 分发到不同 sheet - 通过 `aggregate` 声明派生汇总输出 - 通过 `from` 复用字段集合与容器配置 - 不再支持旧写法: 顶层 `output:`"	null	null	null	"[[{\"fields\":[\"order_id\",\"user_id\"],\"name\":\"detail\",\"to\":{\"sheet\":\"明细\"}}]]"	minItems=0; items=ref #/definitions/output_target
  11	demand.field	validate_unique_field_names	properties.validate_unique_field_names	false	null	boolean	"预检查: 字段有效展示名(`effective display name`)全局唯一. - 默认启用: 未声明时等价 `true` - 有效展示名定义: - 若 `field.name` 非空: 使用 `name` - 否则回退为 `field_id` - 仅当 `effective outputs` 会输出表头且 `header_fields_output_by: name` 时触发 - file: `write.include_header: true` 且 `write.header_fields_output_by: name` - book: 该 output 会输出表头,且 `write.header_fields_output_by: name` - 显式设置为 `false` 可关闭该检查(不推荐长期使用)"	null	true	null	[true,false]	null
  12	demand.field	include_full_error_message	properties.include_full_error_message	false	null	boolean	包含完整错误信息(可能包含敏感信息;默认 false).	null	false	null	[false]	null
  13	demand.definition	book	definitions.book	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2; allOf=2
  14	demand.definition	book_budget	definitions.book_budget	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  15	demand.definition	book_export_xlsx	definitions.book_export_xlsx	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  16	demand.definition	book_write_defaults	definitions.book_write_defaults	false	null	object	null	null	null	null	null	additionalProperties=false
  17	demand.definition	field	definitions.field	false	null	object	null	null	null	null	null	additionalProperties=true; allOf=1
  18	demand.definition	file	definitions.file	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  19	demand.definition	guardrails	definitions.guardrails	false	null	object	null	null	null	null	null	additionalProperties=false
  20	demand.definition	guardrails_compute	definitions.guardrails_compute	false	null	object	null	null	null	null	null	additionalProperties=false
  21	demand.definition	guardrails_loader	definitions.guardrails_loader	false	null	object	null	null	null	null	null	additionalProperties=false
  22	demand.definition	guardrails_relations	definitions.guardrails_relations	false	null	object	null	null	null	null	null	additionalProperties=false
  23	demand.definition	loader_retry	definitions.loader_retry	false	null	object	null	null	null	null	null	additionalProperties=false
  24	demand.definition	main_source	definitions.main_source	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  25	demand.definition	output_aggregate	definitions.output_aggregate	false	null	object	null	null	null	null	null	additionalProperties=false
  26	demand.definition	output_extra_sheet	definitions.output_extra_sheet	false	null	object	null	null	null	null	null	additionalProperties=false
  27	demand.definition	output_target	definitions.output_target	false	null	object	null	null	null	null	null	additionalProperties=false; allOf=1
  28	demand.definition	output_to	definitions.output_to	false	null	object	null	null	null	null	null	additionalProperties=false
  29	demand.definition	output_write	definitions.output_write	false	null	object	null	null	null	null	null	additionalProperties=false
  30	demand.definition	relation	definitions.relation	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  31	demand.definition	resources	definitions.resources	false	null	object	null	null	null	null	null	additionalProperties=false
  32	demand.definition	source	definitions.source	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  33	demand.definition	source_field_inline	definitions.source_field_inline	false	null	object	null	null	null	null	null	allOf=2
  34	workflow	workflow	properties.workflow	true	null	object	null	null	null	null	null	additionalProperties=false
  35	workflow	workflow.runs[*]	properties.workflow.properties.runs.items	false	null	object	null	null	null	null	null	additionalProperties=false
  36	workflow	workflow.options	properties.workflow.properties.options	false	null	object	null	null	null	null	null	additionalProperties=false
  37	workflow	workflow.resources	properties.workflow.properties.resources	false	null	null	"workflow-scope shared IO resources. - stable surface: `workflow.resources.books` / `workflow.resources.files`"	null	{}	null	null	allOf=1
properties[119	]{entry_id	name	required	summary}:
  6	$import	false	string | array, oneOf(2)
  7	$import	false	string | array, oneOf(2)
  8	$import	false	string | array, oneOf(2)
  13	$import	false	string | array, oneOf(2)
  13	allow_formulas	false	boolean
  13	budget	false	allOf(1)
  13	export_xlsx	false	allOf(1)
  13	kind	false	string, enum xlsx_file, xlsx_memory
  13	path	false	string | object, oneOf(2)
  13	write_defaults	false	allOf(1)
  13	write_lock	false	boolean
  14	$import	false	string | array, oneOf(2)
  14	max_sheets	false	integer
  14	max_total_cells	false	integer
  15	$import	false	string | array, oneOf(2)
  15	allow_formulas	false	boolean
  15	path	false	string | object, oneOf(2)
  15	write_lock	false	boolean
  16	$import	false	string | array, oneOf(2)
  16	align_by	false	string, enum field_id, header
  16	header_policy	false	string, enum once, always, never
  16	mode	false	string, enum sheet, append
  16	on_conflict	false	string, enum error, overwrite, skip
  16	on_mismatch	false	string, enum error, warn, skip
  17	name	false	string
  17	$import	false	string | array, oneOf(2)
  17	call_by	false	string
  17	compute	false	string
  17	extract	false	string
  17	relation	false	string | object, oneOf(2)
  17	source	false	string
  17	value_cast	false	string, enum auto, int, str, decimal
  18	$import	false	string | array, oneOf(2)
  18	encoding	false	string
  18	kind	false	string, enum csv_file
  18	path	false	string | object, oneOf(2)
  19	relations	false	ref #/definitions/guardrails_relations
  19	$import	false	string | array, oneOf(2)
  19	compute	false	ref #/definitions/guardrails_compute
  19	enabled	false	boolean
  19	loader	false	ref #/definitions/guardrails_loader
  19	mode	false	string, enum quiet, fast_fail
  20	$import	false	string | array, oneOf(2)
  20	on_error	false	string, enum quiet, fast_fail
  21	$import	false	string | array, oneOf(2)
  21	on_transform_error	false	string, enum quiet, fast_fail
  21	required_fields	false	array, items string | object, anyOf(2)
  21	validate_result	false	boolean
  22	$import	false	string | array, oneOf(2)
  22	null_key_max_rate	false	number
  22	type_error_max_rate	false	number
  23	$import	false	string | array, oneOf(2)
  23	backoff	false	string, enum fixed, exponential
  23	base_delay_seconds	false	number
  23	enabled	false	boolean
  23	jitter	false	boolean
  23	max_attempts	false	integer
  23	max_delay_seconds	false	number
  23	max_elapsed_seconds	false	number
  23	should_retry	false	string
  24	fields	false	object, properties $import
  24	$import	false	string | array, oneOf(2)
  24	loader	false	string
  24	order_by	false	array, items string
  24	params	false	object, properties $import
  24	source_id	false	string
  25	fields	true	object
  25	distinct_on_overflow	false	string, enum error, truncate
  25	group_by	true	array, items string | object | array, anyOf(3)
  25	max_distinct	false	integer
  25	max_groups	false	integer
  26	allow_formulas	false	boolean
  26	path	false	string
  26	sheet	false	string
  26	write_lock	false	boolean
  27	name	true	string
  27	fields	false	array, items string | object | array, anyOf(3)
  27	aggregate	false	allOf(1)
  27	from	false	string
  27	to	false	allOf(1)
  27	where	false	string
  27	write	false	allOf(1)
  28	book	false	string
  28	file	false	string
  28	sheet	false	string
  29	header_fields_output_by	false	string, enum field_id, name
  29	include_header	false	boolean
  30	$import	false	string | array, oneOf(2)
  30	steps	false	array, items object, properties from, lookup_cast, to
  31	$import	false	string | array, oneOf(2)
  31	books	false	object, properties $import
  31	files	false	object, properties $import
  32	fields	false	object, properties $import
  32	$import	false	string | array, oneOf(2)
  32	cache_mode	false	string, enum none, preload_forever
  32	key	false	string | array, oneOf(2)
  32	loader	false	string
  32	lookup_cast	false	object, properties name, sep
  32	lookup_chunk_size	false	integer | null, oneOf(2)
  32	normalize	false	object, properties fields, call_by, key_field, kind, on_conflict, on_empty, on_missing, steps, allOf(1)
  32	params	false	object, properties $import
  33	name	false	string
  33	$import	false	string | array, oneOf(2)
  33	extract	false	string
  33	relation	false	string | object, oneOf(2)
  33	source	false	string
  33	value_cast	false	string, enum auto, int, str, decimal
  34	resources	false	allOf(1)
  34	options	false	object, properties cache_pool, ctx, failure_policy, max_concurrency
  34	runs	true	array, items object, properties demand, depends_on, id, init_vars, main_rows_from
  35	demand	true	string
  35	depends_on	false	array, items string
  35	id	true	string
  35	init_vars	false	object | null, oneOf(2)
  35	main_rows_from	false	object | null, oneOf(2)
  36	cache_pool	false	object | null, oneOf(2)
  36	ctx	false	object | null, oneOf(2)
  36	failure_policy	false	string, enum all_fail, primary_only
  36	max_concurrency	false	integer
workflow_key_paths[10	]: workflow.runs	workflow.runs[*].id	workflow.runs[*].demand	workflow.runs[*].depends_on	workflow.runs[*].init_vars	workflow.options	workflow.options.ctx	workflow.options.cache_pool	workflow.resources	workflow.resources.books
workflow_validation[2	]: "Repo schema-only: uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>"	"LSP header: # yaml-language-server: $schema=.../workflow.gen.json OR # $schema: .../workflow.gen.json (use yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>)"
```
