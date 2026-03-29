# yaml-dsl-schema Specification

**状态: ✅ 已实现**
## Purpose
通过 dataclass 元数据生成 YAML DSL JSON Schema(`demand.gen.json`),作为校验与编辑器提示的唯一来源.
## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/models/__init__.py` (schema meta dataclasses)
- `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/constants.py` (enum/hover fragments)
- `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/builder.py` (schema builder + writer)
- `scripts/gen-yaml-dsl-schema.py` (single generation entrypoint)
- `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` (generated artifact)
- `tests/test_yaml_schema_generation.py` (drift guard)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validator.py` (runtime strict validation)
## Implementation Notes (Current Behavior)
本节描述 **实际代码链路**,用于避免“规范/实现”理解偏差.

### Generation Pipeline (as implemented)
- **Schema 元数据来源**:
  - `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/models/__init__.py` 定义 dataclass + `_schema_meta(...)` 元数据
  - `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/constants.py` 提供枚举/描述/默认值/基础 schema 片段
  - `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/builder.py` 默认通过轻量 adapter 统一访问 models/constants(不再保留 `schema_dsl/types.py` 聚合模块)
- **Schema 构建器**:
  - `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/builder.py::SchemaBuilder.build_demand_schema()`
  - 关键实际行为:
    - 顶层 `properties` 由 `DemandConfig` + `DEMAND_SCHEMA_PROPERTIES_ORDER` 构造
    - `fields` 顶层使用自定义描述与 `FIELD_DERIVED_CONDITIONS` 约束
    - `source_field` + `derived_field` 通过 `_build_field_definition()` 合并
    - 生成 schema 包含 `$comment`,值为“自动生成, 请勿手动修改...”
- **输出写入**:
  - `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/builder.py::write_demand_schema()` 使用 `json.dump(..., ensure_ascii=False, indent=2, sort_keys=False)` 写出
- **命令入口**:
  - `scripts/gen-yaml-dsl-schema.py` 是唯一生成入口
  - `just gen-yaml-dsl-schema` 调用该脚本,输出到 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **一致性验证**:
  - `tests/test_yaml_schema_generation.py` 校验生成结果与 `demand.gen.json` 一致,并要求存在 `$comment`

### Schema vs. Runtime Validation
- `demand.gen.json` 用于 **编辑器提示 / schema-only 校验**(例如 `PROJECT_CLI_NAME yaml-dsl schema validate`).
- 运行时严格校验由 `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validator.py` 执行,可能比 schema 更严格(例如 schema 对 `fields` 允许额外键,但严格校验会报告未知字段).
## Requirements
### Requirement: enums and defaults MUST be sourced from schema_dsl SSOT

系统 MUST 将 YAML DSL 的枚举/默认值/描述文本收敛到 schema_dsl 作为单点 SSOT.

约束:
- runtime validator/parser MUST 引用 schema_dsl 的导出,不得复制同一份枚举/默认值常量
- 系统 MUST 提供一致性自检（测试或脚本），确保 schema 接受的枚举与 runtime 接受的枚举一致

#### Scenario: enum drift is detected
- **WHEN** 维护者修改 schema_dsl 中某个 enum/默认值
- **AND** runtime validator/parser 未同步（出现不一致）
- **THEN** 一致性自检 MUST fail-fast 并指出不一致字段

### Requirement: schema 元数据生成与 hover 指引
系统 SHALL 使用 `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/` 的元数据(见 `constants.py` 与 `models/__init__.py`)生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` 并将其视为唯一 canonical schema.
- schema 顶层不包含 `dsl_version`
- schema 顶层仅保留 `relations`(排除 `relations_sql_like`/`relations_graph`)
- `relations.steps.from/to` 支持 `source.field` 字符串或同源字符串列表
- 数组字段 `items_choices` 映射为 `items.enum`
- schema 提供 steps/fields/sources/params 的中文 hover 描述与示例
- 对枚举/choices 字段提供简洁 hover 说明(逐项解释语义)并附带示例

#### Scenario: 生成器不产出 dsl_version
- **WHEN** 执行 schema 生成脚本
- **THEN** `demand.gen.json` 顶层不包含 `dsl_version` 属性

#### Scenario: Schema 支持 step 点号表达式
- **WHEN** 执行 schema 生成脚本
- **THEN** `steps.from` 与 `steps.to` SHALL 通过 `oneOf` 接受字符串或字符串数组

#### Scenario: enum hover 说明与示例
- **WHEN** 执行 schema 生成脚本
- **THEN** `output.format`/`output.header_fields_output_by`/`value_cast`/`lookup_cast.name`/`performance.report.format`/`relations.report.format`/`observability.viz.payload_policy` 的 `markdownDescription` 均包含选项语义说明且具备示例值
- **AND** `output.path` 的 `markdownDescription` MUST 说明相对路径以进程 CWD 为基准、会自动创建父目录且可能覆盖同名文件(并提示不要对不可信 YAML 开启文件输出)

### Requirement: schema 为 `value_cast` 增加 `decimal` 枚举值
系统 MUST 在生成的 YAML DSL JSON Schema 中为源字段 `value_cast` 提供枚举值 `decimal`,并在 hover 文案中说明其语义为“转换为 `Decimal`”.

#### Scenario: schema 生成结果包含 decimal
- **WHEN** 运行 schema 生成脚本
- **THEN** `demand.gen.json` 中 `value_cast` 的 enum MUST 包含 `decimal`

### Requirement: outputs 字段 hover 指引明确可选与 overrides 推荐写法
系统 MUST 在生成的 YAML DSL JSON Schema 中,为顶层 `outputs` 字段提供清晰的 `markdownDescription`,并明确:
- 顶层 `outputs` 为可选字段(用于保持 demand YAML 可复用);
- 当把 demand YAML 当作“需求本体模板”复用时,推荐在 Python 调用侧使用 `overrides.outputs` 运行期指定输出编排。

#### Scenario: schema 中包含 outputs 可选与 overrides.outputs 提示
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `properties.outputs.markdownDescription` MUST 提及 `outputs` 可选
- **AND** `properties.outputs.markdownDescription` MUST 提及 `overrides.outputs` 的推荐用法

### Requirement: `header_fields_output_by` default is `name`
系统 MUST 将 `outputs[*].container.header_fields_output_by` 的 schema 默认值设为 `name`(破坏性变更).

#### Scenario: schema default for header_fields_output_by is name
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `definitions.output_container.properties.header_fields_output_by.default` MUST 等于 `name`

### Requirement: schema exposes a switch for unique effective field display names
系统 MUST 在 schema 中暴露一个 YAML authoring 侧开关,用于控制“字段有效展示名(effective display name)全局唯一”的预检查策略。

该开关 MUST:
- 位于顶层;
- 名称为 `validate_unique_field_names`(boolean);
- 默认语义为启用(未声明时等价 `true`);
- hover 文案 MUST 解释“有效展示名”的定义: `field.name` 非空则取 `name`,否则回退为 `field_id`。
- hover 文案 MUST 说明该预检查仅在 effective outputs 使用 `container.include_header: true`(显式或默认) 且 `container.header_fields_output_by: name` 时触发。

#### Scenario: schema 生成结果包含顶层校验开关
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** schema MUST 暴露 `properties.validate_unique_field_names`

### Requirement: schema hover 提供常见错误与迁移提示
系统 MUST 在 YAML DSL JSON Schema 的关键字段上提供可读且简短的常见错误/迁移提示,以提升编辑器 LSP 体验并减少试错成本:

- `relations.*.steps.from/to` 的 hover MUST 提示 steps 仅接受 **field_id**(YAML key)而非 loader 的 data_key,并给出简短示例.
- `lookup_cast` 的 hover MUST 提示 float lookup key 会被拒绝(避免歧义)并建议通过 `lookup_cast`/`value_cast` 显式归一化.
- `main_source.params`/`sources.*.params` 的 hover MUST 解释 `{$init_var: <name>}`/`$keys/$rows` 的用法与限制,并说明 legacy `bind/to_bind` 已移除并迁移到 `params` 模板.

#### Scenario: hover 包含 field_id/data_key 提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `relations.*.steps.from/to` 的 `markdownDescription` MUST 提及 field_id 与 data_key 的区别并包含示例

#### Scenario: hover 包含 float key 策略提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `lookup_cast` 的 `markdownDescription` MUST 提示 float 被拒绝并给出修复建议

### Requirement: schema hover documents `$keys/$rows` directive nodes under `params`
系统 MUST 在生成的 YAML DSL JSON Schema 中,为 `main_source.params` 与 `sources.*.params` 提供明确的 hover 文档,解释:
- `$keys` 指令节点的用途、`as=set|list` 选项与最小示例
- `$rows` 指令节点的用途、`cache_mode=batch|none` 选项与最小示例
- `$rows` 会触发 rows barrier(并行退化)的提示
- `$keys/$rows` 仅在 ref loader 上下文可用,main_source/preload 禁止

#### Scenario: params hover 包含 `$keys/$rows` 示例
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `main_source.params` 与 `sources.*.params` 的 `markdownDescription` MUST 包含 `$keys/$rows` 指令节点说明与示例片段

### Requirement: `params` hover documents `{$runtime: <name>}` and preload params behavior
Schema 生成器 MUST 在 `main_source.params` 与 `sources.*.params` 的 hover/markdownDescription 中清晰说明:
- `main_source.params` 作为 kwargs 直接透传给 main source loader
- `sources.<id>.params` 作为 loader kwargs 模板,在对应 loader 被调用时透传(包含 preload_forever 的预加载调用)
- `{$init_var: <name>}` 可用于引用初始化变量,并在编译期被解析为调用方提供的 `init_vars[<name>]`

#### Scenario: schema hover 不再声称 preload_forever 零参调用
- **WHEN** 生成 `demand.gen.json`
- **THEN** `sources.*.params` 的 markdownDescription MUST 不再包含“preload_forever 预加载调用为无参”的旧描述

### Requirement: 顶层 schema 字段(guardrails)
系统 SHALL 在 YAML DSL schema 顶层新增可选对象 `guardrails` 用于运行时护栏配置.
`guardrails.mode` 仅允许 `quiet|fast_fail`;`loader.on_transform_error` 与 `compute.on_error` 仅允许 `quiet|fast_fail`;
`loader.validate_result` 为布尔值(可选);`loader.required_fields` 为数组(可选),条目允许为 `field_id` 字符串或对象(alias);
`relations.null_key_max_rate` 与 `relations.type_error_max_rate` 为 0-1 的浮点数(可选);
不提供 `relations.fields` 范围选择器(关联阈值护栏默认对全部关联 lookup step 生效).

#### Scenario: guardrails schema 可选
- **WHEN** YAML 未提供 `guardrails`
- **THEN** schema 校验通过

#### Scenario: guardrails 非法枚举
- **WHEN** `guardrails.mode: panic`
- **THEN** schema 校验失败并指出非法枚举值

### Requirement: observability.logging 支持 renderer/preset 字段
系统 MUST 在 YAML DSL 的 `observability.logging` 配置中提供可扩展的 renderer/preset(字符串枚举)字段,用于选择 logging 组件的输出实现,以替代对外运行入口中的 `pretty_logging: bool` 开关.
schema MUST 对该字段提供 hover 说明与示例值.

#### Scenario: schema 包含 renderer 字段
- **WHEN** 执行 schema 生成脚本
- **THEN** `demand.gen.json` 中 `observability.logging` MUST 包含 renderer/preset 字段且具备 enum 值与说明

#### Scenario: renderer=pretty 通过校验
- **WHEN** 用户配置 `observability.logging.renderer: pretty`
- **THEN** schema-only 与运行时校验均应通过

### Requirement: schema hover 说明 loader 引用支持相对模块语法
系统 MUST 在 YAML DSL JSON Schema 中为 `main_source.loader` / `sources.*.loader` / `*.retry.should_retry` 的 hover 文案说明 loader 引用格式,并明确:
- 支持绝对引用 `module.path.function` / `module.path:obj.method`
- 支持以 `.` / `..` 开头的相对 module path(相对 YAML 文件所在目录)
- 相对引用解析后仍受 allowlist(`allowed_modules`/`allowed_functions`)约束

#### Scenario: loader hover 提示包含相对引用示例
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `main_source.loader` 的 `markdownDescription` MUST 包含至少一个相对引用示例(例如 `.loaders:load_orders`)

### Requirement: 字段声明位置与 compute 约束
系统 SHALL 支持在 `main_source.fields` 与 `sources.*.fields` 内声明源字段,顶层 `fields` 仅用于派生字段且必须包含 `compute`.
顶层 `fields` 可缺省或为空映射;schema 允许字段对象包含额外键,但严格校验脚本可报告未知字段.

#### Scenario: 顶层 fields 出现源字段
- **WHEN** 顶层 `fields` 中声明无 `compute` 的字段
- **THEN** 校验必须失败并提示仅允许派生字段

### Requirement: schema documents `extract` as current-row-relative field extraction
系统 MUST 在 YAML DSL JSON Schema 的源字段定义中新增 `extract` 字段,并在 `description` / `markdownDescription` 中明确说明:
- `extract` 相对当前 key 对应的 row value 解析
- 系统只隐式省略最外层 `lookup_key -> value` 包装
- row value 内部的包裹层不会被自动跳过

schema 示例 MUST 至少包含:
- `extract: CustomerMark.clearn_reason_level`
- `extract: "[1].clearn_reason_level"`
- `extract: '["a.b"]'`
- `extract: review_status`

#### Scenario: schema hover 包含 current-row-relative 说明
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** 源字段定义中的 `extract` MUST 具备 `description` 或 `markdownDescription`
- **AND** 其文案 MUST 明确说明 `extract` 不是相对整个 loader-result mapping 解析

### Requirement: schema removes legacy `field` and provides migration guidance
系统 MUST 从源字段 schema 中移除 `field`,并在 hover/文档中明确说明:
- 源字段取值唯一入口是 `extract`
- rename 也用 `extract: <key_name>`
- 若出现历史 `field: ...`,应按迁移错误处理并提示改为 `extract: ...`

#### Scenario: schema 不再暴露 `field`
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** 源字段定义 MUST NOT 包含可用的 `field` 属性(应通过 schema/validator 拒绝)

### Requirement: relation steps-only 约束
系统 SHALL 将 `fields.*.relation` 限制为 steps 对象(允许 YAML alias 复用),禁止 relation_id 字符串引用.

#### Scenario: relation_id 字符串被拒绝
- **WHEN** `fields.*.relation` 使用字符串引用
- **THEN** 校验必须失败并提示仅支持 steps 对象

### Requirement: output.fields 解析与 schema 指引
系统 SHALL 仅接受 `output.fields` 条目为对象(dict/alias),并支持以下解析方式;拒绝字符串、单键映射与签名匹配形式.

支持的条目类型:
- **Alias 条目**: 条目为字段定义处 dict 的直接 YAML alias(同一对象),系统 MUST 通过对象身份反查到对应字段定义并解析其 `field_id`.
- **显式选择器条目**: 条目为 dict,系统 MUST 按以下规则解析:
  - 若条目包含 `field_id`,系统 MUST 将其作为选择器按 `field_id` 定位字段定义;可选 `source` 用于跨 source 重名时消歧义.
  - 若条目不包含 `field_id` 但包含 `field`,系统 MUST 将其作为选择器按 loader data_key 定位**源字段(kind=source)**;可选 `source` 用于消歧义.
  - 对歧义场景系统 MUST 报错并提示补充 `source` 或改用 alias/`field_id`:
    - `field_id` 跨 source 重名且缺省 `source`
    - `field`(data_key) 在多个 source 存在且缺省 `source`
    - `field`(data_key) 在同一 source 内匹配到多个字段定义

显式条目的覆写项为除选择器键之外的其它键,用于覆写字段定义(例如 `name`/`relation`/`value_cast` 等):
- 使用 `field_id` 选择时,选择器键为 `field_id`(以及可选 `source`)
- 使用 `field` 选择时,选择器键为 `field`(以及可选 `source`)

schema 的 `description`/`markdownDescription`/示例 MUST 展示:
- Alias 复用
- 显式 `{field_id: ...}` 选择器
- 显式 `{field: <data_key>, source?: ...}` 选择器
并明确说明 YAML merge(`<<`) 会丢失对象身份,merge 产物需要选择器键才能解析.

#### Scenario: output 使用显式 field_id 对象
- **WHEN** `output.fields` 包含 `{field_id: order_id, name: "Order ID"}`
- **THEN** 解析器解析 `order_id` 并应用 name 覆盖

#### Scenario: output 使用显式 field(data_key) 选择器对象
- **GIVEN** source `orders` 定义字段 `order_name: {extract: order_real_name}`
- **WHEN** `output.fields` 包含 `{field: order_real_name, source: orders, name: "Order Name"}`
- **THEN** 解析器解析到 `orders.order_name` 并应用 name 覆盖

#### Scenario: output 使用字符串 field_id
- **WHEN** `output.fields` 包含 `"order_id"`
- **THEN** 解析器必须报错并提示改用显式对象条目

#### Scenario: field(data_key) 跨 source 歧义需要 source
- **GIVEN** source `orders` 与 source `customers` 均存在 data_key 为 `id` 的源字段
- **WHEN** `output.fields` 包含 `{field: id}` 且未提供 `source`
- **THEN** 校验必须失败并提示补充 `source` 或改用 `field_id`

#### Scenario: merge 产物缺少选择器报错
- **GIVEN** `*order_id` 为字段定义 dict 的 alias 且该 dict 不包含 `field` 键
- **WHEN** `output.fields` 包含 `{<<: *order_id, name: "Order ID (override)"}`
- **THEN** 校验必须失败并提示 merge 产物必须包含 `field_id` 或 `field` 选择器

### Requirement: 字段 ID 唯一性与解析规则
系统 SHALL 要求源字段 `field_id` 在单个 source 内唯一;派生字段 `field_id` 全局唯一且不得与任何源字段同名.
系统 SHALL 允许源字段 `field_id` 采用 `<source_id>.<field_id>` 命名约定并视为普通字符串;同一 source 内多个字段可引用相同 `data_key`(例如多个字段的 `extract` 为同一个顶层 key),但 `field_id` 不同.
当 `output.fields` 缺省且存在跨 source 同名 `field_id` 时,校验必须失败并提示必须显式指定 `output.fields`.

#### Scenario: 派生/源同名 field_id
- **WHEN** 顶层 `fields` 与 `main_source.fields`/`sources.*.fields` 使用相同 `field_id`
- **THEN** 校验必须失败并提示派生/源同名不允许

字段剪枝与 required-fields 闭包语义详见 `runtime-pruning`.

### Requirement: 派生字段支持 call_by Schema
Schema 生成器 SHALL 在派生字段定义中加入 `call_by` 字段,类型为字符串,并在 schema hover 中说明 `reference(args...)` 语法、kwargs 示例、Python 字面量示例与 `$ctx.*` 可用属性( `row_id`/`batch_num`/`field_id`/`deps`/`values` ).
schema hover MUST 明确 `reference` 的 module path 同时支持:
- 绝对引用: `module.path.function` / `module.path:obj.method`
- 相对引用: 以 `.` / `..` 开头的 module path(相对 YAML 文件所在目录)
Schema SHALL 对派生字段声明 `compute` 与 `call_by` 做互斥约束(oneOf),并确保源字段/主源字段不允许出现 `call_by`.

#### Scenario: call_by 仅允许派生字段
- **WHEN** `main_source.fields` 或 `sources.*.fields` 中出现 `call_by`
- **THEN** schema 校验失败并提示仅允许派生字段

#### Scenario: call_by 语法说明可见且包含相对引用
- **WHEN** 在 LSP/Schema hover 查看 `call_by`
- **THEN** 显示函数引用格式、kwargs 示例与 `$ctx.*` 可用属性说明
- **AND** hover MUST 包含至少一个相对引用示例(例如 `.helpers:to_text(status)`)

#### Scenario: compute/call_by 互斥
- **WHEN** 同一派生字段同时声明 `compute` 与 `call_by`
- **THEN** schema 校验失败并提示互斥约束

### Requirement: schema meta key 参考文档与推荐写法
系统 MUST 提供一份可发现的 schema meta key 参考,用于约束与指导 `_schema_meta(...)` 的使用.
该参考 MUST 至少包含:
- 支持的 shorthand keys/别名(例如 `md/markdown`, `desc`, `choices`, `items_choices` 等)与其对应的 JSONSchema 字段;
- 推荐的 canonical 写法(例如推荐使用 `md` 而不是 `markdown`);
- 可复制的示例(至少覆盖 `schema_name`, `md`, `choices`, `example/examples`, `items_choices`).

#### Scenario: 新同事查阅 schema meta key
- **WHEN** 用户需要为 YAML DSL schema 增加 hover 描述/枚举/示例并使用 `_schema_meta(...)`
- **THEN** 系统应提供一份集中参考,列出可用 key 与推荐写法,并包含可复制示例

### Requirement: schema meta 中 schema dict 不得吞掉 desc/md
系统 MUST 在生成 YAML DSL JSON Schema 时保留 `_schema_meta(...)` 中除 `schema` 之外的 meta 信息(例如 `desc`/`md`/`examples` 等),以避免 LSP hover 缺失.

#### Scenario: main_source.order_by hover 可见
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `definitions.main_source.properties.order_by` MUST 包含 `description` 或 `markdownDescription`(至少其一)以支持编辑器 hover

### Requirement: schema 明确 batch_size 的 null-or-int 语义
Schema 生成器 MUST 将顶层 `batch_size` 定义为 `oneOf`:
- `type: "null"`(语义:禁用分批)
- `type: "integer"` 且 `minimum: 1`(语义:固定分批)

schema hover/markdownDescription MUST 明确区分三种状态:
- 未声明:沿用默认分批策略.
- 显式 `null`:no-chunking(单批执行).
- 显式整数:按固定批大小分批.

#### Scenario: schema 接受 null
- **WHEN** 配置 `batch_size: null`
- **THEN** schema 校验 MUST 通过

#### Scenario: schema 拒绝非法值
- **WHEN** 配置 `batch_size` 为 `0` 或 `-1` 或 `1.5` 或 `true` 或 `"oops"`
- **THEN** schema 校验 MUST 失败并指向 `batch_size`

### Requirement: retry 字段纳入 JSON Schema 与 hover 指引
系统 SHALL 在生成的 YAML DSL JSON Schema(`demand.gen.json`)中新增:
- 顶层可选对象 `retry`
- `main_source` 下的可选对象 `retry`
- `sources.*` 下的可选对象 `retry`

Schema MUST 为 retry policy 字段提供:
- 类型约束(bool/int/number/enum)
- 范围约束(至少包含硬上限:`max_attempts<=5`、`max_elapsed_seconds<=20`、`max_delay_seconds<=5`)
- 简短 hover 指引,说明安全默认值与“默认不启用”的语义

#### Scenario: schema 允许缺省 retry
- **WHEN** YAML 配置不包含任意 `retry` 字段
- **THEN** schema 校验 MUST 通过

#### Scenario: schema 拒绝超过硬上限
- **WHEN** YAML 配置包含 `retry.max_attempts: 6`
- **THEN** schema 校验 MUST 失败并指出字段路径

### Requirement: `_templates.retry.*` 受 schema 校验但 `_templates` 其它内容保持 freeform
系统 MUST 在 schema 中为 `_templates.retry` 定义结构:其为一个对象映射(template_name -> retry policy 对象).
系统 MUST 保持 `_templates` 的其它内容为 freeform(不要求 schema 穷举/校验),但 `_templates.retry.*` MUST 按 retry policy 规则校验.

#### Scenario: `_templates.retry` 中的非法枚举被拒绝
- **WHEN** `_templates.retry.db_default.backoff: \"random\"`
- **THEN** schema 校验 MUST 失败并指出字段路径

### Requirement: schema 说明源代码级 `normalize` 及其执行顺序
系统 MUST 在 YAML DSL JSON Schema 的 `sources.*` 定义中新增 `normalize` 字段,并在 `description` / `markdownDescription` 中明确说明:
- `normalize` 是源代码级整体结果归一化
- `normalize` 先于字段级 `extract` 执行
- `normalize.kind=index_by_key` 的输入输出形状示例

#### Scenario: schema hover 包含 `index_by_key` 形状示例
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `sources.*.normalize` 的文案 MUST 展示 `list[row] -> key -> row` 的示例
- **AND** MUST 明确说明该能力不是字段级提取

### Requirement: schema keeps `normalize` out of `main_source`
系统 MUST NOT 在 `main_source` schema 中暴露 `normalize` 字段。

#### Scenario: `main_source` schema 无 `normalize`
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `definitions.main_source.properties` MUST NOT 包含 `normalize`

### Requirement: `outputs.*.fields` 支持 YAML alias 条目
系统 MUST 允许 `outputs[*].fields` 的每一项为以下两种之一:
- `field_id` 字符串
- YAML alias(object) 条目: 条目为某个“已定义字段对象”的 alias(展开后为 dict),系统 MUST 将其解析为该字段对象对应的 `field_id`

字段对象的来源包括:
- `main_source.fields.*`
- `sources.*.fields.*`
- 顶层派生字段 `fields.*`

#### Scenario: `outputs.*.fields` 使用 main_source 字段 alias
- **GIVEN** `main_source.fields.quantity: &quantity {...}` 定义了字段对象
- **WHEN** `outputs[0].fields` 包含条目 `- *quantity`
- **THEN** 校验 MUST 通过且解析后的 `outputs[0].fields` MUST 包含 `quantity` 作为 `field_id`

#### Scenario: `outputs.*.fields` 使用 derived 字段 alias
- **GIVEN** 顶层 `fields.profit: &profit {compute: ...}` 定义了派生字段对象
- **WHEN** `outputs[0].fields` 包含条目 `- *profit`
- **THEN** 校验 MUST 通过且解析后的 `outputs[0].fields` MUST 包含 `profit` 作为 `field_id`

### Requirement: alias identity 失败时允许唯一内容匹配
当 `outputs[*].fields` 的 object 条目无法通过“对象身份”(identity)反查到字段对象时,系统 SHALL 允许基于内容相等做兜底匹配,但仅当匹配结果唯一时才允许成功解析.

#### Scenario: content match 唯一匹配成功
- **GIVEN** `outputs[0].fields[0]` 为一个 dict,其内容与某个已定义字段对象内容相等且仅能匹配到一个字段
- **WHEN** 系统解析 `outputs`
- **THEN** 该条目 MUST 被解析为该字段的 `field_id`

#### Scenario: content match 歧义时 fail-fast
- **GIVEN** `outputs[0].fields[0]` 的 dict 内容可匹配到多个字段对象
- **WHEN** 系统解析 `outputs`
- **THEN** 校验 MUST 失败并提示该条目歧义,并建议改用 string `field_id`

#### Scenario: content match 找不到时 fail-fast
- **GIVEN** `outputs[0].fields[0]` 的 dict 内容无法匹配任何字段对象
- **WHEN** 系统解析 `outputs`
- **THEN** 校验 MUST 失败并提示该条目无法解析为 `field_id`,并建议改用 string `field_id`

### Requirement: schema 允许 `outputs.*.fields` 包含 object 条目
系统 MUST 在生成的 YAML DSL JSON Schema 中允许 `outputs[*].fields.items` 为 `string | object`,以避免 schema-only 校验与编辑器提示拦截 alias 写法.

#### Scenario: schema validate 不因 object 条目直接失败
- **GIVEN** `outputs[0].fields` 包含 YAML alias(object) 条目
- **WHEN** 执行 schema-only 校验
- **THEN** 校验 MUST NOT 因 `outputs[0].fields[*]` 的类型为 object 而失败

### Requirement: schema 覆盖 `outputs.*.container.path` 的 `{$init_var: <name>}` 语法

系统 MUST 在 YAML DSL JSON Schema 中继续支持 `outputs[*].container.path` 使用 `{$init_var: <name>}` 指令节点注入输出路径,但该能力仅作为 **CSV 文件输出** 的最小子集保留:

- 仅当 `outputs[*].container.type: csv` 时允许
- `outputs[*].container.path` MUST 支持:
  - 非空静态字符串路径
  - 或 `{$init_var: <name>}` 指令节点(对象节点,不是字符串插值)
- `outputs[*].container.path: \"\"`(空字符串) MUST 被拒绝(见本变更对 pathless CSV 的移除)

说明:

- `.xlsx` 输出路径注入 MUST 迁移为 `resources.books.*.path` / `export_xlsx.path`(见本变更新增 requirements)。

#### Scenario: schema validate accepts string or init_var object for csv output paths
- **WHEN** 执行 demand schema-only 校验且 `outputs[0].container.type=csv` 且 `outputs[0].container.path={$init_var: output_path}`
- **THEN** 校验 MUST 通过

### Requirement: schema MUST support `{$init_var: <name>}` for book export paths
系统 MUST 在 YAML DSL JSON Schema 中对以下路径字段支持 `{$init_var: <name>}` 指令节点(对象节点,不是字符串插值):

- demand: `resources.books.*.path` (当 `kind=xlsx_file`)
- demand/workflow: `*.resources.books.*.export_xlsx.path` (当 `kind=xlsx_memory` 且启用导出)

其中 `{$init_var: <name>}` 在 schema 层的结构 MUST 满足:

- YAML 值为 object(mapping)
- object MUST 仅包含 key `"$init_var"`
- `"$init_var"` 的 value MUST 为非空字符串
- object MUST `additionalProperties=false`

#### Scenario: schema validate accepts string or init_var object for book paths
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` 与 `workflow.gen.json`
- **THEN** book 的 `path`/`export_xlsx.path` 字段 MUST 通过 `oneOf` 接受 string 或 `{$init_var: <name>}` object

### Requirement: demand schema MUST reject legacy output container types and shapes (`workbook`, pathless `csv`)

系统 MUST 在 demand schema-only 校验阶段拒绝以下已移除/不再作为主路径的形态:

- `outputs[*].container.type: workbook`
- `outputs[*].container.type: csv` 且 `outputs[*].container.path: ""`

#### Scenario: workbook container type is rejected by schema
- **WHEN** 执行 demand schema-only 校验且 `outputs[0].container.type=workbook`
- **THEN** 校验 MUST 失败

#### Scenario: pathless csv is rejected by schema
- **WHEN** 执行 demand schema-only 校验且 `outputs[0].container.type=csv` 且 `outputs[0].container.path=\"\"`
- **THEN** 校验 MUST 失败

### Requirement: workflow schema MUST reject legacy workflow IO fields (`writes`, `workbooks`, `csvs`, `sheetbooks`)

系统 MUST 在 workflow JSON schema 中拒绝已移除的 workflow IO authoring surface:

- `workflow.runs[*].writes`
- `workflow.resources.workbooks`
- `workflow.resources.csvs`
- `workflow.resources.sheetbooks`

并要求 workflow 的共享 IO 统一通过:

- `workflow.resources.books`

#### Scenario: workflow schema rejects removed `writes`
- **WHEN** 执行 workflow schema-only 校验且出现 `workflow.runs[0].writes`
- **THEN** 校验 MUST 失败

#### Scenario: workflow schema rejects legacy resources
- **WHEN** 执行 workflow schema-only 校验且出现 `workflow.resources.sheetbooks`
- **THEN** 校验 MUST 失败

