# Scalim YAML DSL Syntax Catalog

此文档由 `scripts/gen-agent-skill.py` 自动生成.

## Canonical Sources
- Demand schema: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Workflow schema: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- Canonical example: `references/generated/example-full/ecommerce_report.gen.yaml`
- Runtime semantic validator: `src/scalim/dsl/by_yaml/config_parsing/validator.py`

## Top-Level Fields
- `name`
- `imports`
- `$import`
- `_templates`
- `description`
- `batch_size`
- `retry`
- `main_source`
- `sources`
- `fields`
- `relations`
- `guardrails`
- `outputs`
- `failure_policy`
- `include_full_error_message`
- `meta`
- `audit`
- `observability`

## Definitions
- `field`
- `guardrails`
- `guardrails_compute`
- `guardrails_loader`
- `guardrails_relations`
- `loader_retry`
- `logging`
- `main_source`
- `memory_opt`
- `observability`
- `output_aggregate`
- `output_container`
- `output_extra_sheet`
- `output_target`
- `performance`
- `performance_report`
- `performance_thresholds`
- `relation`
- `relation_report`
- `relations`
- `row_gap`
- `source`
- `source_field_inline`
- `trace`
- `viz`

## OpenSpec Requirement Map
### `yaml-dsl-schema`
- Source: `openspec/specs/yaml-dsl-schema/spec.md`
- Purpose: 通过 dataclass 元数据生成 YAML DSL JSON Schema(`demand.gen.json`),作为校验与编辑器提示的唯一来源.
- Requirements:
  - schema 元数据生成与 hover 指引
  - schema 为 `value_cast` 增加 `decimal` 枚举值
  - output 字段 hover 指引明确可选与 overrides 推荐写法
  - schema hover 提供常见错误与迁移提示
  - schema hover documents `$keys/$rows` directive nodes under `params`
  - `params` hover documents `{$runtime: <name>}` and preload params behavior
  - 顶层 schema 字段(guardrails)
  - observability.logging 支持 renderer/preset 字段
  - schema hover 说明 loader 引用支持相对模块语法
  - 字段声明位置与 compute 约束
  - schema documents `extract` as current-row-relative field extraction
  - schema removes legacy `field` and provides migration guidance
  - relation steps-only 约束
  - output.fields 解析与 schema 指引
  - 字段 ID 唯一性与解析规则
  - 派生字段支持 call_by Schema
  - schema meta key 参考文档与推荐写法
  - schema meta 中 schema dict 不得吞掉 desc/md
  - schema 明确 batch_size 的 null-or-int 语义
  - retry 字段纳入 JSON Schema 与 hover 指引
  - `_templates.retry.*` 受 schema 校验但 `_templates` 其它内容保持 freeform
  - schema 说明源代码级 `normalize` 及其执行顺序
  - schema keeps `normalize` out of `main_source`
  - `outputs.*.fields` 支持 YAML alias 条目
  - alias identity 失败时允许唯一内容匹配
  - schema 允许 `outputs.*.fields` 包含 object 条目
  - schema 覆盖 `outputs.*.container.path` 的 `{$init_var: <name>}` 语法
  - schema MAY allow pathless CSV outputs for workflow-managed temp outputs
### `demand-dsl`
- Source: `openspec/specs/demand-dsl/spec.md`
- Purpose: 实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.
- Requirements:
  - 顶层结构与 IR 转换规则
  - unknown fields 诊断提供 suggestions(CLI/库一致)
  - Loader 引用解析与 allowlist
  - Source/Bind 结构与 keys 分片参数
  - loader params templates support `{$runtime: <name>}` directives
  - 字段/关系表达式默认行为
  - main_source 批次排序配置
  - 顶层 batch_size 语义统一且可显式禁用分批
  - batch_size 校验在不同入口语义一致
  - YAML DSL 增加 loader retry 配置入口
  - `_templates.retry` 用于复用通用策略
  - `should_retry` 引用解析与 allowlist
  - `normalize` is allowed on `sources.*` and rejected on `main_source`
  - aggregate derived fields MUST support dependency-driven evaluation (DAG)
  - aggregate fields MUST support safe compute derived fields (`compute`)
### `yaml-dsl-workflow`
- Source: `openspec/specs/yaml-dsl-workflow/spec.md`
- Purpose: 提供独立于 demand 的 workflow YAML,用于编排多个 demand 的批量执行,支持并发上限、失败策略与可选的 workflow-scope cache pool(用于共享 `preload_forever` 等缓存条目).
- Requirements:
  - Workflow YAML declares runs and options
  - Runs execute demand YAML via existing compilation pipeline
  - Workflow enforces failure_policy
  - max_concurrency limits parallel runs deterministically
  - workflow nodes declare explicit DAG deps via `depends_on`
  - workflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)
  - ctx guardrails MUST be configurable via `workflow.options.ctx`
  - demand nodes MUST publish a minimal default ctx summary
  - `$ctx` directives are resolved during compile-on-ready materialization
  - failure propagation cancels downstream nodes deterministically
  - workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
  - workflow entrypoints MUST be importable under Python 3.6
  - workflow emits workflow-level events and injects attribution for demand events
  - max_concurrency>1 requires thread-safe or stateless components
### `source-relations`
- Source: `openspec/specs/source-relations/spec.md`
- Purpose: 使用 `relations.*.steps` 描述主数据源到目标数据源的有序等值关联链,支持单步/多步/多字段关联,并在关联查找前应用 `lookup_cast` 归一化,执行时保持 left join 语义.
- Requirements:
  - steps 结构与 relation 解析/推断规则
  - lookup_key 与 lookup_cast/诊断
  - ref loader params are expressed by target-source params templates
  - `$rows` preserves rows barrier semantics for relations
  - preload_forever sources reject `$keys/$rows` directives
  - legacy `to_bind` is rejected with a copy-pastable migration hint
  - 批次内 LoadRef 复用与分片语义
  - ref loader 依赖信号驱动稳定排序
  - 关联诊断基于样本值并支持复合键对比
  - 关联路径与比较输出可读且稳定
  - relation `from` MAY reference pre-relation derived fields on main_source side
### `field-compute`
- Source: `openspec/specs/field-compute/spec.md`
- Purpose: 定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略.
- Requirements:
  - 字段值 value_cast
  - compute 识别/校验/安全约束
  - compute 表达式允许使用 `Decimal(...)` 构造器
  - 依赖推导规则与无依赖拒绝
  - 派生字段执行与错误处理
  - compute 表达式预编译并复用执行
  - compute 编译缓存有上限(有界 LRU)
  - call_by 派生字段函数调用
  - call_by 上下文引用
  - compute sandbox rejection MUST include an actionable `call_by` migration hint
### `source-cache`
- Source: `openspec/specs/source-cache/spec.md`
- Purpose: 支持 cache_mode=preload_forever 的数据源在 pipeline 启动前预加载,结果写入 ExecutionRuntime.preloaded_cache 并在关联加载时复用;计划元数据记录已缓存的数据源.
- Requirements:
  - 预加载缓存模式
  - 关联加载优先命中缓存
  - 计划元数据记录缓存源
  - preload cache stores normalized source results
  - `preloaded_cache` concurrency boundary and key space MUST be explicit
  - `PreloadCache` signature guardrail MUST be available (opt-in)
  - loader SHOULD be idempotent when concurrent / repeated loads are possible
### `workflow-cache-pool`
- Source: `openspec/specs/workflow-cache-pool/spec.md`
- Purpose: 提供 workflow-scope 的缓存池(`cache_pool`),用于在同一次 workflow 执行内跨 nodes 复用可共享缓存条目(当前主要用于 `preload_forever` 结果),并通过 signature-based keys/冲突策略/生命周期(refcount+pin)/预算策略/观测事件确保“复用正确且可诊断”.
- Requirements:
  - workflow options expose a stable `cache_pool` configuration (replacing `share_preload_cache`)
  - workflow provides a cache pool with signature-based keys
  - cache pool defines an explicit conflict policy
  - cache pool supports lifecycle management and auto-release
  - cache pool refcount MUST be derived from Workflow IR when available
  - cache pool enforces budgets with a clear policy
  - cache pool MUST be observable via workflow-level events
### `workflow-shared-output-containers`
- Source: `openspec/specs/workflow-shared-output-containers/spec.md`
- Purpose: TBD - created by archiving change c30-workflow-shared-output-containers. Update Purpose after archive.
- Requirements:
  - workflow YAML exposes a stable authoring surface for shared resources and write intents
  - workflow declares shared output resources at workflow scope
  - shared output is written via explicit workflow write nodes
  - writes to shared resources are deterministic and serialized
  - append/merge semantics are explicit and verifiable
  - shared resources commit atomically at workflow end
  - shared resource lifecycle MUST be observable
  - shared resource plan creation MUST be atomic and joinable within a workflow exec
### `workflow-sheetbook-resources`
- Source: `openspec/specs/workflow-sheetbook-resources/spec.md`
- Purpose: 定义 workflow YAML 的 sheetbook 资源(authoring surface)、预算护栏与写入 intent(`writes[*].sheetbook_*`)契约,并要求写入行为确定性、冲突安全、可观测且可原子导出为最终 xlsx,同时提供内置 loader 供下游节点读取 sheet rows.
- Requirements:
  - workflow YAML exposes a stable authoring surface for sheetbooks
  - workflow MUST support in-memory sheetbook resources
  - writes to a sheetbook MUST be deterministic and conflict-safe
  - workflow MUST support exporting a sheetbook to an Excel workbook atomically
  - demand nodes MUST be able to consume sheetbook sheet rows via a built-in loader
  - workflow MUST precheck Excel output-path collisions across nodes
  - sheetbook lifecycle MUST be observable and joinable
  - sheetbook plan creation MUST be atomic within a workflow exec
### `workflow-observability-bridge`
- Source: `openspec/specs/workflow-observability-bridge/spec.md`
- Purpose: 定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约,使 demand 事件可稳定归因到 workflow 节点,并提供最小的 workflow-level 编排事件.
- Requirements:
  - workflow attributes demand events for stable DAG correlation
  - workflow provides workflow-level observability events
  - workflow preserves demand hooks/observers semantics
  - workflow event catalog is extensible for cache/resources
### `runtime-pruning`
- Source: `openspec/specs/runtime-pruning/spec.md`
- Purpose: PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.
- Requirements:
  - 依赖剪枝与计划元数据
  - YAML 转换阶段按 output.fields 剪枝字段定义
  - 运行时字段保留与释放策略
### `loader-retry-policy`
- Source: `openspec/specs/loader-retry-policy/spec.md`
- Purpose: TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.
- Requirements:
  - Loader retry policy 配置模型与默认值
  - should_retry 回调契约
  - Retry runner 语义(次数/耗时/退避)
  - 全局策略与 per-loader 覆盖的解析
  - iterable/generator 的重试边界
### `runtime-guardrails`
- Source: `openspec/specs/runtime-guardrails/spec.md`
- Purpose: 定义运行期 guardrails 配置与执行契约,用于对 loader/relations/compute 等环节的契约违规、数据质量问题与异常处理提供可配置的 quiet/fast_fail 行为,并通过现有错误事件通道进行可观测记录.
- Requirements:
  - Guardrails 配置与默认行为
  - quiet 模式违规记录
  - Loader 结果结构护栏
  - RowLike 字段提取语义(无歧义优先级)
  - 关键字段缺失护栏
  - 字段 extractor/value_cast/transform 异常护栏
  - 关联 null_key/type_error 阈值护栏
  - compute 异常护栏
  - GuardrailViolation payload 包含稳定的 guardrail 元字段
  - quiet 模式下的 guardrail once_key 去重约定
### `performance-observability`
- Source: `openspec/specs/performance-observability/spec.md`
- Purpose: PerformanceObserver 在 pipeline/batch/loader 事件上收集耗时、loader 统计与吞吐量,并可选采样内存/CPU(psutil 可选);RelationObserver 收集关联命中率与类型不匹配诊断.
- Requirements:
  - 性能指标采集与结构化输出
  - duration 统计使用单调时钟
  - 资源采样与报告输出
  - Observability DSL 配置与独立开关
  - RelationObserver 统计与报告
  - adaptive 调度决策可观测性
### `output-mode-api`
- Source: `openspec/specs/output-mode-api/spec.md`
- Purpose: 定义运行时输出语义为“显式 sink 驱动”: 是否保留内存数据、是否写文件、以及是否同时写入(tee)都通过 sink 选择表达,而不是通过 `return_data` 等布尔参数驱动 runtime 隐式装配. 同时要求稳定的执行元数据(例如 `ExecutionResult.total_rows`)以及异常路径的 best-effort 资源清理.
- Requirements:
  - 输出是否保留内存数据由 sink 表达
  - 无输出时避免构造返回列表
  - 允许 tee 同时写文件与显式 sink
  - total_rows 为稳定元数据
  - 成功路径 sink.close 失败必须使 run 失败
  - 异常路径 close 不得覆盖原异常
  - 异常路径 best-effort 关闭 sink

## Top-Level Field Details
### `name`
- Type: `string`
- Description:
  需求配置名称.
  
  - 必填, 用于标识当前配置
- Examples: `order_report`

### `imports`
- Type: `object`
- Description:
  片段文件导入别名映射.
  
  - key: alias
  - value: 片段文件路径(字符串)
  - V2 支持相对路径 fragments(解析基准: 当前 YAML 文件所在目录):
    - `./x.yaml` / `x.yaml`
    - `x/y.yaml`(子目录)
    - `../x.yaml`(父目录)
  - 支持(编辑器侧放宽,运行时校验为准):
    - alias 路径: `@/x.yaml`, `COMMON:/x.yaml`(需 `scalim.yaml` 显式配置)
    - 内置 preset: `scalim://yaml-dsl/presets/common.yaml`(仅本地白名单)
  - 禁止(以运行时为准): 绝对路径/非 `scalim://` 的 `URI scheme`/Windows 盘符/反斜杠分隔符等
- `additionalProperties`: `string`

### `$import`
- Type: `string` | `array`
- Description:
  $import 引用.
  
  - string: `<alias>(.<segment>)*`
  - list: 按顺序合并,后者覆盖前者,最终再被本地覆盖
  - 仅支持 mapping 片段
  - V1 仅支持同级文件导入(见顶层 `imports`)
- Examples: `common.sources`, `["common.sources", "other.sources"]`
- `oneOf`:
  - 1. `string`
  - 2. `array`, items `string`

### `_templates`
- Type: `object`
- Description:
  YAML anchor 模板集合.
  
  - 仅用于 YAML 复用(anchors)
  - 常用于 `fields` / `relations` / `retry`
- `additionalProperties`: `true`
- Properties:
  - `retry`: `object`

### `description`
- Type: `string`
- Description:
  配置描述(可选).

### `batch_size`
- Type: `null` | `integer`
- Description:
  批处理大小.
  
  - 未声明时使用默认值
  - `null` 表示禁用分批(单批执行)
  - `>=1` 的整数表示固定分批大小
- Default: `1000`
- Examples: `null`, `1000`
- `oneOf`:
  - 1. `null`
  - 2. `integer`

### `retry`
- Description:
  Loader retry 策略.
  
  - 默认关闭: `enabled: false`
  - 启用后会对 loader 调用的瞬态错误做有限重试
  - 需要提供 `should_retry` 回调(安全引用),用于决定是否重试
  - 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5
- `allOf`:
  - 1. ref `#/definitions/loader_retry`

### `main_source`
- Description:
  主数据源配置.
  
  - 必填: `source_id`, `loader`
  - `source_id` 不能出现在 `sources` 中
  - `fields` 仅允许源字段(禁止 `compute`)
  - `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)
- `allOf`:
  - 1. ref `#/definitions/main_source`

### `sources`
- Type: `object`
- Description:
  数据源配置映射, key 为 `source_id`.
  
  - 每个 source 必填: `loader`, `key`
  - 不允许包含 `main_source.source_id`
  - `fields` 仅允许源字段(禁止 `compute`)
- `minProperties`: `0`
- `additionalProperties`: ref `#/definitions/source`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)

### `fields`
- Type: `object`
- Description:
  字段配置映射(仅用于派生字段).
  
  - 必须包含 `compute` 或 `call_by`
  - 不能与源字段同名(避免 source/derived 重名)
  - 支持 YAML anchor 复用
- `additionalProperties`: ref `#/definitions/field`

### `relations`
- Type: `object`
- Description:
  命名关联关系映射(steps 模板).
  
  - 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用
  - string ref: `relation: <relation_id>` 引用 `relations.<relation_id>`
  - alias 复用: `relation: *<anchor>` (YAML anchor)
  - steps 必须是等值关联链, 参考 `relation.steps`
- `additionalProperties`: ref `#/definitions/relation`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)

### `guardrails`
- Description:
  运行时护栏配置.
  
  - 默认关闭
  - 用于控制 loader/relations/compute 等运行期护栏策略
- `allOf`:
  - 1. ref `#/definitions/guardrails`

### `outputs`
- Type: `array`
- Description:
  输出目标列表(有序).
  
  - 通过 `where` 分发到不同 sheet
  - 通过 `aggregate` 声明派生汇总输出
  - 通过 `from` 复用字段集合与容器配置
  - 不再支持旧写法: 顶层 `output:`
- Examples: `[{"container": {"path": "./output/report.xlsx", "sheet": "明细", "type": "workbook"}, "fields": ["order_id", "user_id"], "name": "detail"}]`
- `minItems`: `0`
- `items`: ref `#/definitions/output_target`

### `failure_policy`
- Type: `string`
- Description:
  多输出失败策略.
  
  - `all_fail`: 任一目标失败即失败
  - `primary_only`: 非主输出失败将被禁用但不阻断主输出
- Enum: `all_fail`, `primary_only`
- Default: `all_fail`
- Examples: `all_fail`

### `include_full_error_message`
- Type: `boolean`
- Description:
  包含完整错误信息(可能包含敏感信息;默认 false).
- Default: `False`
- Examples: `false`

### `meta`
- Type: `boolean` | ref `#/definitions/output_extra_sheet`
- Description:
  可选:启用 meta sheet.
  
  - `true` 表示启用并使用默认配置
  - 对象形式可覆盖 sheet 名称与 workbook 路径
- Examples: `true`, `{"sheet": "__meta__"}`
- `oneOf`:
  - 1. `boolean`
  - 2. ref `#/definitions/output_extra_sheet`

### `audit`
- Type: `boolean` | ref `#/definitions/output_extra_sheet`
- Description:
  可选:启用 audit sheet.
  
  - `true` 表示启用并使用默认配置
  - 对象形式可覆盖 sheet 名称与 workbook 路径
- Examples: `true`, `{"sheet": "__audit__"}`
- `oneOf`:
  - 1. `boolean`
  - 2. ref `#/definitions/output_extra_sheet`

### `observability`
- Description:
  可观测性配置.
  
  包含 `logging`、`performance`、`relations`、`viz`、`trace`、`row_gap` 与 `memory_opt` 子配置.
- `allOf`:
  - 1. ref `#/definitions/observability`


## Definition Details
### `field`
- Definition path: `definitions.field`
- Type: `object`
- `additionalProperties`: `true`
- `allOf`:
  - 1. oneOf(2)
- Properties:
  - `name`: `string`
  - `$import`: `string` | `array`, oneOf(2)
  - `call_by`: `string`
  - `compute`: `string`
  - `extract`: `string`
  - `relation`: `string` | `object`, oneOf(2)
  - `source`: `string`
  - `value_cast`: `string`, enum `auto`, `int`, `str`, `decimal`

### `guardrails`
- Definition path: `definitions.guardrails`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `relations`: ref `#/definitions/guardrails_relations`
  - `compute`: ref `#/definitions/guardrails_compute`
  - `enabled`: `boolean`
  - `loader`: ref `#/definitions/guardrails_loader`
  - `mode`: `string`, enum `quiet`, `fast_fail`

### `guardrails_compute`
- Definition path: `definitions.guardrails_compute`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `on_error`: `string`, enum `quiet`, `fast_fail`

### `guardrails_loader`
- Definition path: `definitions.guardrails_loader`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `on_transform_error`: `string`, enum `quiet`, `fast_fail`
  - `required_fields`: `array`, items `string` | `object`, anyOf(2)
  - `validate_result`: `boolean`

### `guardrails_relations`
- Definition path: `definitions.guardrails_relations`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `null_key_max_rate`: 关联 null_key 最大比例(0.0-1.0;未设置则不启用)
  - `type_error_max_rate`: 关联 type_error 最大比例(0.0-1.0;未设置则不启用)

### `loader_retry`
- Definition path: `definitions.loader_retry`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `backoff`: `string`, enum `fixed`, `exponential`
  - `base_delay_seconds`: 基础等待时间(秒)
  - `enabled`: `boolean`
  - `jitter`: `boolean`
  - `max_attempts`: `integer`
  - `max_delay_seconds`: 最大单次等待时间(秒)
  - `max_elapsed_seconds`: 最大累计耗时(秒,包含 sleep)
  - `should_retry`: `string`

### `logging`
- Definition path: `definitions.logging`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `enabled`: `boolean`
  - `renderer`: `string`, enum `pretty`, `logger`

### `main_source`
- Definition path: `definitions.main_source`
- Type: `object`
- `additionalProperties`: `false`
- `anyOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `retry`: allOf(1)
  - `fields`: `object`, properties `$import`
  - `loader`: `string`
  - `order_by`: `array`, items `string`
  - `params`: `object`, properties `$import`
  - `source_id`: `string`

### `memory_opt`
- Definition path: `definitions.memory_opt`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `auto_report`: `boolean`
  - `enabled`: `boolean`
  - `max_fields`: `integer`

### `observability`
- Definition path: `definitions.observability`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `relations`: allOf(1)
  - `logging`: allOf(1)
  - `memory_opt`: allOf(1)
  - `performance`: allOf(1)
  - `row_gap`: allOf(1)
  - `trace`: allOf(1)
  - `viz`: allOf(1)

### `output_aggregate`
- Definition path: `definitions.output_aggregate`
- Type: `object`
- `additionalProperties`: `false`
- `anyOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `fields`: `object`
  - `distinct_on_overflow`: `string`, enum `error`, `truncate`
  - `group_by`: `array`, items `string` | `object` | `array`, anyOf(3)
  - `max_distinct`: `integer`
  - `max_groups`: `integer`

### `output_container`
- Definition path: `definitions.output_container`
- Type: `object`
- `additionalProperties`: `false`
- `anyOf`:
  - 1. `object`
  - 2. `object`
- `allOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `allow_formulas`: `boolean`
  - `encoding`: `string`
  - `header_fields_output_by`: `string`, enum `field_id`, `name`
  - `include_header`: `boolean`
  - `path`: `string` | `string` | `object`, oneOf(3)
  - `sheet`: `string`
  - `streaming`: `boolean`
  - `type`: `string`, enum `workbook`, `csv`
  - `write_lock`: `boolean`

### `output_extra_sheet`
- Definition path: `definitions.output_extra_sheet`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `allow_formulas`: `boolean`
  - `path`: `string`
  - `sheet`: `string`
  - `write_lock`: `boolean`

### `output_target`
- Definition path: `definitions.output_target`
- Type: `object`
- `additionalProperties`: `false`
- `anyOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `name`: `string`
  - `$import`: `string` | `array`, oneOf(2)
  - `fields`: `array`, items `string` | `object` | `array`, anyOf(3)
  - `aggregate`: allOf(1)
  - `container`: allOf(1)
  - `from`: `string`
  - `where`: `string`

### `performance`
- Definition path: `definitions.performance`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `enabled`: `boolean`
  - `metrics`: `array`, items enum `duration`, `memory`, `cpu`
  - `report`: ref `#/definitions/performance_report`
  - `sampling_interval`: `integer`
  - `thresholds`: ref `#/definitions/performance_thresholds`

### `performance_report`
- Definition path: `definitions.performance_report`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `format`: `string`, enum `console`, `json`, `csv`, `none`
  - `include_details`: `boolean`
  - `output`: `string`

### `performance_thresholds`
- Definition path: `definitions.performance_thresholds`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `batch_duration_warn`: 批次耗时告警阈值(秒)
  - `memory_increase_warn`: 内存增长告警阈值(MB)

### `relation`
- Definition path: `definitions.relation`
- Type: `object`
- `additionalProperties`: `false`
- `anyOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `steps`: `array`, items `object`, properties `from`, `lookup_cast`, `to`

### `relation_report`
- Definition path: `definitions.relation_report`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `format`: `string`, enum `console`, `json`, `none`
  - `output`: `string`

### `relations`
- Definition path: `definitions.relations`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `enabled`: `boolean`
  - `log_type_mismatch`: `boolean`
  - `max_samples`: `integer`
  - `report`: ref `#/definitions/relation_report`
  - `sampling_rate`: 采样率(0.0-1.0)

### `row_gap`
- Definition path: `definitions.row_gap`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `data_loader_names`: `array`, items `string`
  - `enabled`: `boolean`
  - `primary_loader_name`: `string`
  - `sample_limit`: `integer`

### `source`
- Definition path: `definitions.source`
- Type: `object`
- `additionalProperties`: `false`
- `anyOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `retry`: allOf(1)
  - `fields`: `object`, properties `$import`
  - `cache_mode`: `string`, enum `none`, `preload_forever`
  - `key`: `string` | `array`, oneOf(2)
  - `loader`: `string`
  - `lookup_cast`: `object`, properties `name`, `sep`
  - `lookup_chunk_size`: `integer` | `null`, oneOf(2)
  - `normalize`: `object`, properties `fields`, `call_by`, `key_field`, `kind`, `on_conflict`, `on_empty`, `on_missing`, `steps`, allOf(1)
  - `params`: `object`, properties `$import`

### `source_field_inline`
- Definition path: `definitions.source_field_inline`
- Type: `object`
- `allOf`:
  - 1. `object`
  - 2. `object`
- Properties:
  - `name`: `string`
  - `$import`: `string` | `array`, oneOf(2)
  - `extract`: `string`
  - `relation`: `string` | `object`, oneOf(2)
  - `source`: `string`
  - `value_cast`: `string`, enum `auto`, `int`, `str`, `decimal`

### `trace`
- Definition path: `definitions.trace`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `enabled`: `boolean`

### `viz`
- Definition path: `definitions.viz`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `$import`: `string` | `array`, oneOf(2)
  - `append`: `boolean`
  - `enabled`: `boolean`
  - `env`: `string`
  - `output_dir`: `string`
  - `output_path`: `string`
  - `payload_policy`: `string`, enum `none`, `summary`, `sample`, `full`
  - `run_name`: `string`
  - `sample_size`: `integer`
  - `snapshot_path`: `string`
  - `trace_enabled`: `boolean`
  - `use_default_output_dir`: `boolean`


## Workflow YAML (Generated)

### Key Paths
- `workflow.runs` (required)
- `workflow.runs[*].id` (required)
- `workflow.runs[*].demand` (required)
- `workflow.runs[*].depends_on` (optional)
- `workflow.runs[*].init_vars` (optional; supports `$ctx` directives)
- `workflow.runs[*].writes` (optional; list of intents)
- `workflow.options` (optional; max_concurrency/failure_policy/cache_pool/ctx)
- `workflow.options.ctx` (optional; ctx guardrails)
- `workflow.options.cache_pool` (optional; workflow-scope cache pool)
- `workflow.resources` (optional; workbooks/csvs/sheetbooks)
- `workflow.resources.workbooks` (optional; shared workbook outputs)
- `workflow.resources.csvs` (optional; shared csv outputs)
- `workflow.resources.sheetbooks` (optional; in-memory sheetbook outputs)

### Validation
- Repo schema-only: `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>`
- LSP header: `# yaml-language-server: $schema=.../workflow.gen.json` 或 `# $schema: .../workflow.gen.json` (推荐用 `yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`)

### `workflow`
- Required: `true`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `options`: `object`, properties `failure_policy`, `cache_pool`, `ctx`, `max_concurrency`
  - `resources`: `object`, properties `csvs`, `sheetbooks`, `workbooks`
  - `runs` (required): `array`, items `object`, properties `demand`, `depends_on`, `id`, `init_vars`, `writes`

### `workflow.runs[*]`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `demand` (required): `string`
  - `depends_on`: `array`, items `string`
  - `id` (required): `string`
  - `init_vars`: `object` | `null`, oneOf(2)
  - `writes`: `array`, items `object` | `object` | `object` | `object` | `object`, oneOf(5)

### `workflow.runs[*].writes`
- Type: `array`
- Description:
  共享输出写入意图列表(可选).
  
  - 缺省/空数组表示无写入意图
  - 每个 item MUST 恰好选择一个 write intent
  - 写入顺序 SSOT: run 顺序 + writes 顺序
- Default: `[]`
- `items`: `object` | `object` | `object` | `object` | `object`, oneOf(5)

### `workflow.options`
- Type: `object`
- `additionalProperties`: `false`
- Properties:
  - `failure_policy`: `string`, enum `all_fail`, `primary_only`
  - `cache_pool`: `object` | `null`, oneOf(2)
  - `ctx`: `object` | `null`, oneOf(2)
  - `max_concurrency`: `integer`

### `workflow.resources`
- Type: `object`
- Description:
  workflow-scope shared output resources.
- `additionalProperties`: `false`
- Properties:
  - `csvs`: `object`
  - `sheetbooks`: `object`
  - `workbooks`: `object`
