# Scalim YAML DSL Syntax Catalog

此文档由 `scripts/gen-agent-skill.py` 自动生成.
为节省 token,主体数据以 TOON 格式给出;使用时建议直接复制下方 code block.

```toon
generated_by: scripts/gen-agent-skill.py
sources:
  demand_schema: src/scalim/dsl/yaml_dsl/schema/demand.gen.json
  workflow_schema: src/scalim/dsl/yaml_dsl/schema/workflow.gen.json
  canonical_example: references/generated/example-full/ecommerce_report.gen.yaml
  validator: src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py
builtin_callables[3	]: ^defaults/default	^defaults/default_of_value_cast	^workflow/book_sheet_rows
demand_top_fields[10	]{name	required}:
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
demand_definitions[20	]: book	book_xlsx	field	file	file_csv_file	guardrails	guardrails_compute	guardrails_loader	guardrails_relations	loader_retry	main_source	output_aggregate	output_extra_sheet	output_target	output_to	output_write	relation	resources	source	source_field_inline
llmanspec_requirement_map[15	]{slug	path	purpose	requirements}:
  yaml-dsl-schema	llmanspec/specs/yaml-dsl-schema/spec.toon	通过 dataclass 元数据生成 YAML DSL JSON Schema，作为校验与编辑器提示的唯一来源。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"YAML DSL JSON Schema generator MUST live in dev tooling and consume core SSOT\nschema generation entrypoint MUST remain single and output location MUST remain\nenums and defaults MUST be sourced from schema_dsl SSOT\nschema 生成器 MUST 支持文档标准化与 hover 指引\ndemand JSON Schema MUST validate source identifiers and reject empty loader/key\nYAML DSL JSON Schemas MUST allow YAML merge key (`<<`) where propertyNames is us\noutputs 字段 hover 指引明确可选与 overrides 推荐写法\nschema MUST expose the unified output target surface and reject legacy surfaces\ndemand JSON Schema MUST encode composed outputs invariants\n`header_fields_output_by` default is `name`\n顶层 schema 字段(guardrails)\n字段声明位置与 compute 约束\nschema documents `extract` as current-row-relative field extraction\nschema removes legacy `field` and provides migration guidance\nrelation steps-only 约束\noutput.fields 解析与 schema 指引\n字段 ID 唯一性与解析规则\n派生字段支持 call_by Schema\nschema meta key 参考文档与推荐写法\nschema meta 中 schema dict 不得吞掉 desc/md\nschema 明确 batch_size 的 null-or-int 语义\nretry 字段纳入 JSON Schema 与 hover 指引\ndemand JSON Schema MUST encode `lookup_cast` as a one-of cast-branch object\nschema 说明源代码级 `normalize` 及其执行顺序\n`outputs.*.fields` 支持 YAML alias 与 object 条目\nschema MUST support `{$init_var: <name>}` for resource paths\nkind-based `if/then` constraints MUST NOT trigger when `kind` is missing\nschema MUST NOT expose runtime policy fields"
  demand-dsl	llmanspec/specs/demand-dsl/spec.toon	实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"顶层结构与 IR 转换规则\nsource_id and sources keys MUST be valid identifiers and validated fail-fast\nunknown fields 诊断提供 suggestions(CLI/库一致)\nLoader 引用解析与 allowlist\ncallable preflight MUST run before building execution request\nSource/Bind 结构与 keys 分片参数\n使用语义清晰的配置 key 常量\nloader params templates support `{$runtime: <name>}` directives\n字段/关系表达式默认行为\nmain_source 批次排序配置\nbatch_size 语义、校验与一致性\nYAML DSL loader retry 配置\n`should_retry` 引用解析与 allowlist\n`normalize` 配置规则\naggregate 派生字段支持依赖驱动求值 (DAG)\naggregate fields 支持 safe compute 派生字段 (`compute`)"
  yaml-dsl-workflow	llmanspec/specs/yaml-dsl-workflow/spec.toon	提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目). [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"workflow public guidance MUST use curated stable entrypoints\nWorkflow YAML declares runs and options\nworkflow demand preloading MUST stay structural\nRuns execute demand YAML via existing compilation pipeline\nWorkflow enforces failure_policy\nworkflow preflight errors MUST be treated as workflow config/compile errors (ind\nmax_concurrency limits parallel runs deterministically\nworkflow nodes declare explicit DAG deps via `depends_on`\nworkflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)\ndemand nodes MUST publish a minimal default ctx summary\n`$ctx` directives are resolved during compile-on-ready materialization\nfailure propagation cancels downstream nodes deterministically\nworkflow options expose a stable `cache_pool` configuration (replacing `share_pr\nworkflow entrypoints MUST be importable under Python 3.6\nworkflow emits workflow-level events and injects attribution for demand events\nmax_concurrency>1 requires thread-safe or stateless components\nworkflow YAML MUST use `workflow.resources.books` and MUST reject `writes` autho\nworkflow.options.resources_wait MUST configure join/wait diagnostics and timeout\nworkflow.options.output_staging MUST configure staging directory and cleanup pol\nworkflow scheduler preset MUST be configured through runtime entrypoints\nyaml_dsl public facade MUST export scheduler preset types under a stable import\n`run_workflow(...)` MUST orchestrate parse/preload/effective-merge/preflight via"
  yaml-dsl-books-resources	llmanspec/specs/yaml-dsl-books-resources/spec.toon	定义 demand/workflow 统一的 `resources.books` Excel IO 资源入口,并约束 `outputs[*].to` / `outputs[*].write` 的 book 绑定与导出语义. [scope-review-2026-07-12-c5-openpyxl-helpers]	"books MUST declare exactly one xlsx identity branch\npathful xlsx.path MUST define file export semantics and path resolution\ndemand MUST bind outputs to books via `outputs[*].to.book` and `outputs[*].to.sh\nstandalone demand MUST fail-fast when a referenced book resource is missing\nworkflow MUST merge books from demand/workflow with deterministic precedence and\nworkflow book patches MUST be applied with strict contracts and consistent diagn\nbook write behavior MUST come from Python policy; outputs.write stays header-local\nExcel exports MUST escape formulas for pathful xlsx books\nbook_sheet_rows MUST support unified xlsx pathful and pathless books\n`.xlsx` outputs MUST use books binding; legacy workbook container surface MUST b\nbooks MUST support unified xlsx variant with optional path\nbook runtime identity MUST be pathful vs pathless after normalize\npathless xlsx MUST remain a supported in-memory shared-book pattern\nYAML MUST fail-fast on removed book kind aliases"
  yaml-dsl-output-overrides	llmanspec/specs/yaml-dsl-output-overrides/spec.toon	为下游”UI 动态选字段/动态输出”场景提供单一标准做法：demand YAML 保持可复用（通常不声明 `outputs`），调用侧在 `run/compile` 时通过 typed `RunOverrides` 显式指定输出编排与 IO 覆盖。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"RunOverrides factory methods MUST stay stable including xlsx_file_single_sheet\nlegacy YAML-shaped overrides inputs MUST be rejected with actionable migration h\n`RunOverrides.outputs` MUST take precedence over YAML `outputs`\n`RunOverrides.outputs` MUST compile through the same outputs pipeline\nYAML DSL runtime MUST accept typed `RunOverrides.outputs` (dataclasses)\nRunOverrides.resources MUST remain IO-only for path identity; write/budget use policy API\ndemand compile and workflow compile MUST share the same overrides compilation pi\ninvalid overrides MUST raise ScalimWorkflowConfigError with stable path"
  ir-source-relations	llmanspec/specs/ir-source-relations/spec.toon	使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"steps 结构与 relation 解析/推断规则\nlookup_key 与 lookup_cast/诊断\nref loader params are expressed by target-source params templates\n`$rows` preserves rows barrier semantics for relations\npreload_forever sources reject `$keys/$rows` directives\nlegacy `to_bind` is rejected with a copy-pastable migration hint\n批次内 LoadRef 复用与分片语义\nref loader 依赖信号驱动稳定排序\n关联诊断基于样本值并支持复合键对比\n关联路径与比较输出可读且稳定\nrelation `from` MAY reference pre-relation derived fields on main_source side"
  ir-field-compute	llmanspec/specs/ir-field-compute/spec.toon	定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"字段值 value_cast\ncompute 识别/校验/安全约束\ncompute expression builtin calls MUST validate arity when signature is inspectab\ncompute 安全引擎 MUST provide a safe `dec(x)` decimal helper\ncompute 表达式允许使用 `Decimal(...)` 构造器\n依赖推导规则与无依赖拒绝\n派生字段执行与错误处理\ncompute 表达式预编译并复用执行\ncompute 编译缓存有上限(有界 LRU)\ncompute failures MUST NOT log raw expressions by default\ncompute audit callback MUST support redaction\ncompile cache operations MUST be safe under concurrent access\ncall_by 派生字段函数调用\nderived field call_by MUST validate argument binding at compile time when possib\ncall_by 上下文引用\ncompute sandbox rejection MUST include an actionable `call_by` migration hint"
  execution-source-cache	llmanspec/specs/execution-source-cache/spec.toon	支持 `cache_mode=preload_forever` 的数据源在 pipeline 启动前预加载,结果写入 `ExecutionRuntime.preloaded_cache` 并在关联加载时复用;计划元数据记录已缓存的数据源。对于高频且内存占用小的映射表(如国家地区表、枚举常量映射表),作为全局一次性导入使用以加速获值速度。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"预加载缓存模式\n关联加载优先命中缓存\n计划元数据记录缓存源\npreload cache 存储 normalized 结果\npreloaded_cache 并发边界与 key 空间明确\nPreloadCache signature guardrail 可选启用\nloader 幂等性期望"
  workflow-cache-pool	llmanspec/specs/workflow-cache-pool/spec.toon	"提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件/并发安全确保\"复用正确且可诊断\". [scope-review-2026-07-13-c25-xlsx-ir-path-presence]"	workflow options expose a stable `cache_pool` configuration (replacing `share_pr
  workflow-observability-bridge	llmanspec/specs/workflow-observability-bridge/spec.toon	定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约，使 demand 事件可稳定归因到 workflow 节点，并提供最小的 workflow-level 编排事件。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"workflow attributes demand events for stable DAG correlation\nworkflow provides workflow-level observability events\nworkflow preserves demand hooks/observers semantics\nworkflow event catalog is extensible for cache/resources"
  runtime-pruning	llmanspec/specs/runtime-pruning/spec.toon	PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"依赖剪枝与计划元数据\nYAML 转换阶段按 output.fields 剪枝字段定义\n运行时字段保留与释放策略"
  execution-loader-retry	llmanspec/specs/execution-loader-retry/spec.toon	提供可配置的 loader retry policy 机制，在 loader 调用因瞬态错误失败时执行有限的自动重试，支持全局默认策略与 per-source 覆盖，并通过可配置的退避策略、次数上限和耗时上限防止无限重试。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"Loader retry policy 配置模型与默认值\nshould_retry 回调契约\nshould_retry callback signature MUST be prechecked when enabled\nRetry runner 语义(次数/耗时/退避)\n全局策略与 per-loader 覆盖的解析\niterable/generator 的重试边界"
  runtime-guardrails	llmanspec/specs/runtime-guardrails/spec.toon	定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"Guardrails 配置与默认行为\nruntime guardrails MUST NOT swallow callable preflight failures\nquiet 模式违规记录\nLoader 结果结构护栏\nRowLike 字段提取语义(无歧义优先级)\n关键字段缺失护栏\n字段 extractor/value_cast/transform 异常护栏"
  performance-observability	llmanspec/specs/performance-observability/spec.toon	PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]	"性能指标采集与结构化输出\nduration 统计使用单调时钟\n资源采样与报告输出\nruntime entrypoints 装配与独立开关\nRelationObserver 统计与报告\nadaptive 调度决策可观测性"
  output-mode-api	llmanspec/specs/output-mode-api/spec.toon	"定义运行时输出语义为\"显式 sink 驱动\": 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]"	"输出是否保留内存数据由 sink 表达\n无输出时避免构造返回列表\n允许 tee 同时写文件与显式 sink\ntotal_rows 为稳定元数据\n成功路径 sink.close 失败必须使 run 失败\n异常路径 close 不得覆盖原异常\n异常路径 best-effort 关闭 sink"
entries[33	]{id	scope	key	schema_path	required	ref	type	desc	enum	default	const	examples	constraints}:
  1	demand.field	name	properties.name	true	null	string	"#### name 需求配置名称. - 必填, 用于标识当前配置 ##### 字段约束 - 必填: 是 - 类型: string ##### 例子 ```yaml order_report ```"	null	null	null	"[\"order_report\"]"	null
  2	demand.field	imports	properties.imports	false	null	object	"#### imports 片段文件导入别名映射. - key: alias - value: 片段文件路径(字符串) - V2 支持相对路径 fragments(解析基准: 当前 YAML 文件所在目录): - `./x.yaml` / `x.yaml` - `x/y.yaml`(子目录) - `../x.yaml`(父目录) - 支持(编辑器侧放宽,运行时校验为准): - alias 路径: `@/x.yaml`, `COMMON:/x.yaml`(需 `scalim.yaml` 显式配置) - 内置 preset: `scalim://yaml-dsl/presets/common.yaml`(仅本地白名单) - 禁止(以运行时为准): 绝对路径/非 `scalim://` 的 `URI scheme`/Windows 盘符/反斜杠分隔符等 ##### 字段约束 - 必填: 否 - 类型: object - additionalProperties: string - propertyNames: configured ##### 例子 (兜底最小示例; 仅保证 schema-only 合法) ```yaml {} ```"	null	null	null	null	additionalProperties=string
  3	demand.field	_templates	properties._templates	false	null	object	#### _templates YAML anchor 模板集合. - 仅用于 YAML 复用(anchors) - 常用于 `fields` / `relations`	null	null	null	null	additionalProperties=true
  4	demand.field	description	properties.description	false	null	string	#### description 配置描述(可选).	null	null	null	null	null
  5	demand.field	main_source	properties.main_source	true	null	null	"#### main_source 主数据源配置. - 必填: `source_id`, `loader` - 或仅 `$import`(展开后再校验必填字段)"	null	null	null	null	allOf=1
  6	demand.field	sources	properties.sources	false	null	object	"#### sources 数据源配置映射, key 为 `source_id`. - 每个 source 必填: `loader`, `key` - 不允许包含 `main_source.source_id`"	null	null	null	null	minProperties=0; additionalProperties=ref #/definitions/source
  7	demand.field	fields	properties.fields	false	null	object	#### fields 字段配置映射(仅用于派生字段). - 必须包含 `compute` 或 `call_by` - 不能与源字段同名(避免 source/derived 重名)	null	null	null	null	additionalProperties=ref #/definitions/field
  8	demand.field	relations	properties.relations	false	null	object	"#### relations 命名关联关系映射(steps 模板). - 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用 - string ref: `relation: <relation_id>` 引用 `relations.<relation_id>`"	null	null	null	null	additionalProperties=ref #/definitions/relation
  9	demand.field	resources	properties.resources	false	null	null	"#### resources 可选:IO 资源声明. - 稳定入口: `resources.books` / `resources.files`"	null	null	null	null	allOf=1
  10	demand.field	outputs	properties.outputs	false	null	array	#### outputs 输出目标列表(有序; 可选). - 顶层 `outputs` 可省略,用于保持 demand YAML 可复用(通常仅承载需求本体) - 需要运行时动态指定输出(字段/路径/sheet/header 策略)时,推荐在 Python 调用侧使用与 YAML 同形的 `overrides.outputs`	null	null	null	"[[{\"fields\":[\"order_id\",\"user_id\"],\"name\":\"detail\",\"to\":{\"sheet\":\"明细\"}}]]"	minItems=0; items=ref #/definitions/output_target
  11	demand.definition	book	definitions.book	false	null	object	null	null	null	null	null	additionalProperties=false; allOf=1
  12	demand.definition	book_xlsx	definitions.book_xlsx	false	null	object	null	null	null	null	null	additionalProperties=false
  13	demand.definition	field	definitions.field	false	null	object	null	null	null	null	null	additionalProperties=true; allOf=1
  14	demand.definition	file	definitions.file	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  15	demand.definition	file_csv_file	definitions.file_csv_file	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  16	demand.definition	guardrails	definitions.guardrails	false	null	object	null	null	null	null	null	additionalProperties=false
  17	demand.definition	guardrails_compute	definitions.guardrails_compute	false	null	object	null	null	null	null	null	additionalProperties=false
  18	demand.definition	guardrails_loader	definitions.guardrails_loader	false	null	object	null	null	null	null	null	additionalProperties=false
  19	demand.definition	guardrails_relations	definitions.guardrails_relations	false	null	object	null	null	null	null	null	additionalProperties=false
  20	demand.definition	loader_retry	definitions.loader_retry	false	null	object	null	null	null	null	null	additionalProperties=false
  21	demand.definition	main_source	definitions.main_source	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  22	demand.definition	output_aggregate	definitions.output_aggregate	false	null	object	null	null	null	null	null	additionalProperties=false
  23	demand.definition	output_extra_sheet	definitions.output_extra_sheet	false	null	object	null	null	null	null	null	additionalProperties=false
  24	demand.definition	output_target	definitions.output_target	false	null	object	null	null	null	null	null	additionalProperties=false; allOf=1
  25	demand.definition	output_to	definitions.output_to	false	null	object	null	null	null	null	null	additionalProperties=false
  26	demand.definition	output_write	definitions.output_write	false	null	object	null	null	null	null	null	additionalProperties=false
  27	demand.definition	relation	definitions.relation	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  28	demand.definition	resources	definitions.resources	false	null	object	null	null	null	null	null	additionalProperties=false
  29	demand.definition	source	definitions.source	false	null	object	null	null	null	null	null	additionalProperties=false; anyOf=2
  30	demand.definition	source_field_inline	definitions.source_field_inline	false	null	object	null	null	null	null	null	allOf=3
  31	workflow	workflow	properties.workflow	true	null	object	#### workflow workflow	null	null	null	null	additionalProperties=false
  32	workflow	workflow.runs[*]	properties.workflow.properties.runs.items	false	null	object	null	null	null	null	null	additionalProperties=false
  33	workflow	workflow.resources	properties.workflow.properties.resources	false	null	null	"#### workflow.resources workflow-scope shared IO resources. - stable surface: `workflow.resources.books` / `workflow.resources.files`"	null	{}	null	null	allOf=1
properties[100	]{entry_id	name	required	summary}:
  6	$import	false	string | array, oneOf(2)
  7	$import	false	string | array, oneOf(2)
  8	$import	false	string | array, oneOf(2)
  11	$import	false	string | array, oneOf(2)
  11	xlsx	false	allOf(1)
  12	$import	false	string | array, oneOf(2)
  12	allow_formulas	false	boolean
  12	path	false	string | object, oneOf(2)
  13	name	false	string
  13	$import	false	string | array, oneOf(2)
  13	call_by	false	string
  13	compute	false	string
  13	default	false	array, items object, properties call_by, literal, when, oneOf(2)
  13	extract	false	string
  13	relation	false	string | object, oneOf(2)
  13	source	false	string
  13	value_cast	false	string, enum auto, int, str, decimal
  14	$import	false	string | array, oneOf(2)
  14	csv_file	false	allOf(1)
  15	$import	false	string | array, oneOf(2)
  15	encoding	false	string
  15	path	false	string | object, oneOf(2)
  16	relations	false	ref #/definitions/guardrails_relations
  16	$import	false	string | array, oneOf(2)
  16	compute	false	ref #/definitions/guardrails_compute
  16	enabled	false	boolean
  16	loader	false	ref #/definitions/guardrails_loader
  16	mode	false	string, enum quiet, fast_fail
  17	$import	false	string | array, oneOf(2)
  17	on_error	false	string, enum quiet, fast_fail
  18	$import	false	string | array, oneOf(2)
  18	on_transform_error	false	string, enum quiet, fast_fail
  18	required_fields	false	array, items string | object, anyOf(2)
  18	validate_result	false	boolean
  19	$import	false	string | array, oneOf(2)
  19	null_key_max_rate	false	number
  19	type_error_max_rate	false	number
  20	$import	false	string | array, oneOf(2)
  20	backoff	false	string, enum fixed, exponential
  20	base_delay_seconds	false	number
  20	enabled	false	boolean
  20	jitter	false	boolean
  20	max_attempts	false	integer
  20	max_delay_seconds	false	number
  20	max_elapsed_seconds	false	number
  20	should_retry	false	string
  21	fields	false	object, properties $import
  21	$import	false	string | array, oneOf(2)
  21	loader	false	string
  21	order_by	false	array, items string
  21	params	false	object, properties $import
  21	source_id	false	string
  22	fields	true	object
  22	distinct_on_overflow	false	string, enum error, truncate
  22	group_by	true	array, items string | object | array, anyOf(3)
  22	max_distinct	false	integer
  22	max_groups	false	integer
  23	allow_formulas	false	boolean
  23	path	false	string
  23	sheet	false	string
  24	name	true	string
  24	fields	false	array, items string | object | array, anyOf(3)
  24	aggregate	false	allOf(1)
  24	from	false	string
  24	to	false	allOf(1)
  24	where	false	string
  24	write	false	allOf(1)
  25	book	false	string
  25	file	false	string
  25	sheet	false	string
  26	header_fields_output_by	false	string, enum field_id, name
  26	include_header	false	boolean
  27	$import	false	string | array, oneOf(2)
  27	steps	false	array, items object, properties from, lookup_cast, to
  28	$import	false	string | array, oneOf(2)
  28	books	false	object, properties $import
  28	files	false	object, properties $import
  29	fields	false	object, properties $import
  29	$import	false	string | array, oneOf(2)
  29	cache_mode	false	string, enum none, preload_forever
  29	key	false	string | array, oneOf(2)
  29	loader	false	string
  29	lookup_cast	false	object, oneOf(4)
  29	lookup_chunk_size	false	integer | null, oneOf(2)
  29	normalize	false	object, properties call_by, index_by_key, map_values, project_fields, take_first, allOf(1)
  29	params	false	object, properties $import
  30	name	false	string
  30	$import	false	string | array, oneOf(2)
  30	default	false	array, items object, properties call_by, literal, when, oneOf(2)
  30	extract	false	string
  30	relation	false	string | object, oneOf(2)
  30	source	false	string
  30	value_cast	false	string, enum auto, int, str, decimal
  31	resources	false	allOf(1)
  31	runs	true	array, items object, properties demand, depends_on, id, init_vars, main_rows_from
  32	demand	true	string
  32	depends_on	false	array, items string
  32	id	true	string
  32	init_vars	false	object | null, oneOf(2)
  32	main_rows_from	false	object | null, oneOf(2)
workflow_key_paths[10	]: workflow.runs	workflow.runs[*].id	workflow.runs[*].demand	workflow.runs[*].depends_on	workflow.runs[*].init_vars	workflow.options	workflow.options.ctx	workflow.options.cache_pool	workflow.resources	workflow.resources.books
workflow_validation[2	]: "Repo schema-only: uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>"	"LSP header: # yaml-language-server: $schema=.../workflow.gen.json OR # $schema: .../workflow.gen.json (use yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>)"
```
