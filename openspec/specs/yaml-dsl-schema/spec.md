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
### Requirement: schema 元数据生成与 hover 指引
系统 SHALL 使用 `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/` 的元数据(见 `constants.py` 与 `models/__init__.py`)生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` 并将其视为唯一 canonical schema.
- schema 顶层不包含 `dsl_version`
- schema 顶层仅保留 `relations`(排除 `relations_sql_like`/`relations_graph`)
- `relations.steps.from/to` 支持 `source.field` 字符串或同源字符串列表
- 数组字段 `items_choices` 映射为 `items.enum`
- schema 提供 steps/fields/sources/bind 的中文 hover 描述与示例
- 对枚举/choices 字段提供简洁 hover 说明(逐项解释语义)并附带示例

#### Scenario: 生成器不产出 dsl_version
- **WHEN** 执行 schema 生成脚本
- **THEN** `demand.gen.json` 顶层不包含 `dsl_version` 属性

#### Scenario: Schema 支持 step 点号表达式
- **WHEN** 执行 schema 生成脚本
- **THEN** `steps.from` 与 `steps.to` SHALL 通过 `oneOf` 接受字符串或字符串数组

#### Scenario: enum hover 说明与示例
- **WHEN** 执行 schema 生成脚本
- **THEN** `output.format`/`output.header_fields_output_by`/`value_cast`/`lookup_cast.name`/`bind.use_rows.cache_mode`/`bind.use_keys.as`/`performance.report.format`/`relations.report.format`/`observability.viz.payload_policy` 的 `markdownDescription` 均包含选项语义说明且具备示例值
- **AND** `output.path` 的 `markdownDescription` MUST 说明相对路径以进程 CWD 为基准、会自动创建父目录且可能覆盖同名文件(并提示不要对不可信 YAML 开启文件输出)

### Requirement: output 字段 hover 指引明确可选与 overrides 推荐写法
系统 MUST 在生成的 YAML DSL JSON Schema 中,为顶层 `output` 字段提供清晰的 `markdownDescription`,并明确:
- 顶层 `output` 为可选字段;
- 当把 YAML 当作模板使用时,推荐在 Python 调用侧使用 `overrides.output.*` 覆盖输出策略(例如 `overrides.output.path`).

#### Scenario: schema 中包含可选与 overrides 提示
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `properties.output.markdownDescription` MUST 提及 `output` 可选
- **AND** `properties.output.markdownDescription` MUST 提及 `overrides.output.*` 的推荐用法

### Requirement: schema hover 提供常见错误与迁移提示
系统 MUST 在 YAML DSL JSON Schema 的关键字段上提供可读且简短的常见错误/迁移提示,以提升编辑器 LSP 体验并减少试错成本:

- `relations.*.steps.from/to` 的 hover MUST 提示 steps 仅接受 **field_id**(YAML key)而非 loader 的 data_key,并给出简短示例.
- `lookup_cast` 的 hover MUST 提示 float lookup key 会被拒绝(避免歧义)并建议通过 `lookup_cast`/`value_cast` 显式归一化.
- `to_bind`/`bind` 的 hover MUST 提示 oneOf 结构(`use_keys`/`use_rows`)并给出旧语法迁移提示.

#### Scenario: hover 包含 field_id/data_key 提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `relations.*.steps.from/to` 的 `markdownDescription` MUST 提及 field_id 与 data_key 的区别并包含示例

#### Scenario: hover 包含 float key 策略提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `lookup_cast` 的 `markdownDescription` MUST 提示 float 被拒绝并给出修复建议

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

### Requirement: bind/to_bind oneOf Schema
系统 SHALL 在生成的 schema 中将 bind/to_bind 设为 `use_rows`/`use_keys` oneOf 结构:
- `use_rows` 允许 `param` 与 `cache_mode`(none|batch, 默认 batch)
- `use_keys` 允许 `param` 与 `as`(set|list, 默认 set)

#### Scenario: oneOf 互斥
- **WHEN** bind/to_bind 同时包含 `use_rows` 与 `use_keys`
- **THEN** schema 校验应失败

CLI 校验分层、严格模式、JSON/linter 输出与源码定位见 `yaml-dsl-cli-validation`(本 spec 仅聚焦 schema 生成与 hover 指引).

### Requirement: 派生字段支持 call_by Schema
Schema 生成器 SHALL 在派生字段定义中加入 `call_by` 字段,类型为字符串,并在 schema hover 中说明 `reference(args...)` 语法、kwargs 示例、Python 字面量示例与 `$ctx.*` 可用属性( `row_id`/`batch_num`/`field_id`/`deps`/`values` ).
Schema SHALL 对派生字段声明 `compute` 与 `call_by` 做互斥约束(oneOf),并确保源字段/主源字段不允许出现 `call_by`.

#### Scenario: call_by 仅允许派生字段
- **WHEN** `main_source.fields` 或 `sources.*.fields` 中出现 `call_by`
- **THEN** schema 校验失败并提示仅允许派生字段

#### Scenario: call_by 语法说明可见
- **WHEN** 在 LSP/Schema hover 查看 `call_by`
- **THEN** 显示函数引用格式、kwargs 示例与 `$ctx.*` 可用属性说明

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
