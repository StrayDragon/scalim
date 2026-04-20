# yaml-dsl-schema Specification

**状态: ✅ 已实现**

## Purpose
通过 dataclass 元数据生成 YAML DSL JSON Schema，作为校验与编辑器提示的唯一来源。

## Related Concepts
Schema 元数据模块, Schema 构建器, Schema 文档标准化器, Schema 生成入口脚本, 生成物文件, 运行时校验器, 一致性验证测试

## Requirements

### Requirement: YAML DSL JSON Schema generator MUST live in dev tooling and consume core SSOT

系统 MUST 将 YAML DSL JSON Schema 的**结构/描述 SSOT** 与**生成器实现**分层：

- 结构/描述 SSOT MUST 位于 schema 元数据模块（dataclass + metadata、枚举/默认值、字段描述文本等）。
- JSON Schema 的生成器实现（builder/writer/docs standardization pipeline）MUST 位于 dev tooling packages。
- 生成器 MUST 以 core SSOT 为唯一来源构建 schema，不得在 dev 包中复制字段枚举/默认值/描述文案的另一份真相。
- runtime core MUST NOT 导入 dev tooling packages，包括 optional hook / 动态导入方式。

#### Scenario: changing a field description only touches core SSOT
- **WHEN** 维护者更新某个 YAML 字段的描述性信息
- **THEN** 变更 MUST 只发生在 schema 元数据模块
- **AND** 重新生成后生成器输出 MUST 反映该变更

#### Scenario: missing dev package does not break runtime imports
- **GIVEN** 用户环境未安装 dev tooling 包
- **WHEN** 用户仅使用 runtime 能力或 import 主包
- **THEN** import 与运行 MUST 成功

### Requirement: schema generation entrypoint MUST remain single and output location MUST remain stable

系统 MUST 保持 schema 生成入口与生成物位置为稳定契约：

- 唯一生成入口 MUST 为 schema 生成脚本
- 生成物 MUST 写入 schema 输出目录
- 生成物为 `.gen.` 文件，MUST NOT 手工编辑（只能通过生成入口刷新）

#### Scenario: drift gate points to the single generator entrypoint
- **WHEN** 生成物与生成器输出不一致（drift）
- **THEN** gate MUST fail-fast
- **AND** 输出 MUST 提示运行相应命令以修复

### Requirement: enums and defaults MUST be sourced from schema_dsl SSOT

系统 MUST 将 YAML DSL 的枚举/默认值/描述文本收敛到 schema_dsl 作为单点 SSOT.

约束:
- runtime validator/parser MUST 引用 schema_dsl 的导出，不得复制同一份枚举/默认值常量
- 系统 MUST 提供一致性自检（测试或脚本），确保 schema 接受的枚举与 runtime 接受的枚举一致

#### Scenario: enum drift is detected
- **WHEN** 维护者修改 schema_dsl 中某个 enum/默认值
- **AND** runtime validator/parser 未同步（出现不一致）
- **THEN** 一致性自检 MUST fail-fast 并指出不一致字段

### Requirement: schema 生成器 MUST 支持文档标准化与 hover 指引

系统 SHALL 使用 schema 元数据模块生成 JSON Schema 并将其视为唯一 canonical schema，并提供完整的文档支持：

- schema 顶层不包含 `dsl_version`
- schema 顶层仅保留 `relations`（排除 `relations_sql_like`/`relations_graph`）
- `relations.steps.from/to` 支持 `source.field` 字符串或同源字符串列表
- 数组字段 `items_choices` 映射为 `items.enum`
- schema 提供 steps/fields/sources/params 的中文 hover 描述与示例
- 对枚举/choices 字段提供简洁 hover 说明（逐项解释语义）并附带示例
- schema hover MUST 提供常见错误与迁移提示（包括但不限于 field_id/data_key 区分、float key 策略、legacy 字段迁移）
- schema hover MUST 说明特殊指令节点（包括但不限于 `$keys/$rows`、`$init_var`、相对模块引用）的用法与限制

#### Scenario: 生成器产出正确的 schema 结构
- **WHEN** 执行 schema 生成脚本
- **THEN** 生成 schema MUST 包含正确的顶层结构（不含 dsl_version，保留 relations）
- **AND** MUST 支持点号表达式、枚举映射、hover 描述等特性

#### Scenario: schema hover 包含字段说明与示例
- **WHEN** 生成 schema
- **THEN** 关键字段的 `markdownDescription` MUST 包含选项语义说明且具备示例值
- **AND** MUST 说明相对路径基准、目录创建策略、覆盖风险提示

### Requirement: demand JSON Schema MUST validate source identifiers and reject empty loader/key

系统 MUST 在生成的 YAML DSL JSON Schema 中表达并拒绝以下形态，以与 runtime 语义保持一致：

- `main_source.source_id` MUST 匹配标识符 pattern
- `sources` mapping keys MUST 匹配同一 pattern（通过 `propertyNames`；且为保持 `$import` 在编辑器侧可用，`propertyNames` MUST 同时允许 key 为 `$import`）
- `main_source.loader` / `sources.*.loader` MUST 为非空字符串
- `sources.*.key` 的 string（或 array items） MUST 为合法 `field_id`（拒绝空字符串）

#### Scenario: schema rejects invalid sources configuration
- **WHEN** demand YAML 的 `sources` 出现空 key、非法 key、空 loader 或空 key
- **THEN** schema-only 校验 MUST 失败

### Requirement: YAML DSL JSON Schemas MUST allow YAML merge key (`<<`) where propertyNames is used

系统 MUST 对齐 schema-only 校验与 runtime 的 YAML merge key 支持：

- 对任何使用 `propertyNames` 约束 mapping key 的 object 节点，生成的 schema MUST 显式允许 key 为 `<<`。
- 除 `<<` 之外，原有 `propertyNames` 规则 MUST 保持不变（不得放宽既有命名约束）。

说明：
- 该要求的目标是消除 editor/YAML Language Server 对 merge key 的假阳性，避免用户被迫关闭 schema 或放弃 `<<` 复用。
- runtime 仍是最终语义裁决与严格校验来源；schema-only 的放宽仅用于提升 authoring 体验。

#### Scenario: schema validation accepts merge key in map-like objects
- **GIVEN** 用户的 demand YAML 在 `fields`/`sources`/`imports` 等 mapping 节点使用 YAML merge key
- **WHEN** 编辑器使用生成的 schema 做 schema-only 校验
- **THEN** MUST NOT 报告 `propertyNames` pattern mismatch for key `<<`

### Requirement: outputs 字段 hover 指引明确可选与 overrides 推荐写法

系统 MUST 在生成的 YAML DSL JSON Schema 中，为顶层 `outputs` 字段提供清晰的 `markdownDescription`，并明确：
- 顶层 `outputs` 为可选字段（用于保持 demand YAML 可复用）
- 当把 demand YAML 当作"需求本体模板"复用时，推荐在 Python 调用侧使用 `overrides.outputs` 运行期指定输出编排

#### Scenario: schema 中包含 outputs 可选与 overrides.outputs 提示
- **WHEN** 生成 demand JSON Schema
- **THEN** `properties.outputs.markdownDescription` MUST 提及 `outputs` 可选
- **AND** `properties.outputs.markdownDescription` MUST 提及 `overrides.outputs` 的推荐用法

### Requirement: schema MUST expose the unified output target surface and reject legacy surfaces

系统 MUST 生成反映统一输出模型的 YAML DSL schema：

- MUST 暴露 `resources.files`
- MUST 暴露 `outputs[*].to.file`
- MUST 在 `outputs[*].write` 中暴露通用 header 字段
- MUST NOT 再接受已移除的 legacy surfaces（包括但不限于 `outputs[*].container`、workflow `writes`、workflow `workbooks`/`csvs`/`sheetbooks`）

#### Scenario: schema exposes unified output surfaces
- **WHEN** 生成 demand JSON Schema
- **THEN** schema MUST 暴露统一输出模型的相关定义
- **AND** 顶层 `resources` MUST 支持 `files`

#### Scenario: schema rejects legacy output surfaces
- **WHEN** 用户使用 legacy 输出 surface（包括 container、writes 等）
- **THEN** schema-only 校验 MUST 失败

### Requirement: demand JSON Schema MUST encode composed outputs invariants

系统 MUST 在 demand JSON Schema 中表达 outputs 的关键不变量，避免 schema validate 放行但 parser 失败：

- `outputs[*].container.streaming` 若显式提供，则 MUST 为 `true`
- 当 output 未声明 `aggregate` 时（明细输出），系统 MUST 要求存在字段来源：
  - 显式提供非空 `fields`，或
  - 通过 `from` 继承字段集合
  - 为保持 `$import` 在编辑器侧可用，该约束 MUST 不阻断仅声明 `$import` 的 output_target

#### Scenario: schema rejects invalid composed outputs configuration
- **WHEN** output 配置违反不变量（如 streaming=false 或明细输出缺少字段来源）
- **THEN** schema-only 校验 MUST 失败

### Requirement: `header_fields_output_by` default is `name`

系统 MUST 将统一写入模型下的 `header_fields_output_by` schema 默认值设为 `name`（破坏性变更）。

约束：
- `outputs[*].write.header_fields_output_by.default` MUST 等于 `name`
- `resources.books.write_defaults` MUST NOT 暴露 `header_fields_output_by`

#### Scenario: schema default for header_fields_output_by is name
- **WHEN** 生成 demand JSON Schema
- **THEN** `definitions.output_write.properties.header_fields_output_by.default` MUST 等于 `name`

### Requirement: 顶层 schema 字段(guardrails)

系统 SHALL 在 YAML DSL schema 顶层新增可选对象 `guardrails` 用于运行时护栏配置。

`guardrails.mode` 仅允许 `quiet|fast_fail`；`loader.on_transform_error` 与 `compute.on_error` 仅允许 `quiet|fast_fail`；
`loader.validate_result` 为布尔值（可选）；`loader.required_fields` 为数组（可选），条目允许为 `field_id` 字符串或对象（alias）；
`relations.null_key_max_rate` 与 `relations.type_error_max_rate` 为 0-1 的浮点数（可选）；
不提供 `relations.fields` 范围选择器（关联阈值护栏默认对全部关联 lookup step 生效）。

#### Scenario: guardrails schema 校验
- **WHEN` guardrails 配置缺失或包含非法枚举值
- **THEN** schema 校验 MUST 按预期通过或失败并指出错误

### Requirement: 字段声明位置与 compute 约束

系统 SHALL 支持在 `main_source.fields` 与 `sources.*.fields` 内声明源字段，顶层 `fields` 仅用于派生字段且必须包含 `compute`。
顶层 `fields` 可缺省或为空映射；schema 允许字段对象包含额外键，但严格校验脚本可报告未知字段。

#### Scenario: 顶层 fields 出现源字段
- **WHEN** 顶层 `fields` 中声明无 `compute` 的字段
- **THEN** 校验必须失败并提示仅允许派生字段

### Requirement: schema documents `extract` as current-row-relative field extraction

系统 MUST 在 YAML DSL JSON Schema 的源字段定义中新增 `extract` 字段，并在 `description` / `markdownDescription` 中明确说明：
- `extract` 相对当前 key 对应的 row value 解析
- 系统只隐式省略最外层 `lookup_key -> value` 包装
- row value 内部的包裹层不会被自动跳过

schema 示例 MUST 包含常见 extract 模式（包括嵌套访问、数组索引、特殊键名等）。

#### Scenario: schema hover 包含 current-row-relative 说明
- **WHEN** 生成 demand JSON Schema
- **THEN** 源字段定义中的 `extract` MUST 具备 `description` 或 `markdownDescription`
- **AND** 其文案 MUST 明确说明 `extract` 不是相对整个 loader-result mapping 解析

### Requirement: schema removes legacy `field` and provides migration guidance

系统 MUST 从源字段 schema 中移除 `field`，并在 hover/文档中明确说明：
- 源字段取值唯一入口是 `extract`
- rename 也用 `extract: <key_name>`
- 若出现历史 `field: ...`，应按迁移错误处理并提示改为 `extract: ...`

#### Scenario: schema 不再暴露 `field`
- **WHEN** 生成 demand JSON Schema
- **THEN** 源字段定义 MUST NOT 包含可用的 `field` 属性（应通过 schema/validator 拒绝）

### Requirement: relation steps-only 约束

系统 SHALL 将 `fields.*.relation` 限制为 steps 对象（允许 YAML alias 复用），禁止 relation_id 字符串引用。

#### Scenario: relation_id 字符串被拒绝
- **WHEN** `fields.*.relation` 使用字符串引用
- **THEN** 校验必须失败并提示仅支持 steps 对象

### Requirement: output.fields 解析与 schema 指引

系统 SHALL 仅接受 `output.fields` 条目为对象（dict/alias），并支持以下解析方式；拒绝字符串、单键映射与签名匹配形式。

支持的条目类型：
- **Alias 条目**：条目为字段定义处 dict 的直接 YAML alias（同一对象），系统 MUST 通过对象身份反查到对应字段定义并解析其 `field_id`。
- **显式选择器条目**：条目为 dict，系统 MUST 按以下规则解析：
  - 若条目包含 `field_id`，系统 MUST 将其作为选择器按 `field_id` 定位字段定义；可选 `source` 用于跨 source 重名时消歧义。
  - 若条目不包含 `field_id` 但包含 `field`，系统 MUST 将其作为选择器按 loader data_key 定位**源字段（kind=source）**；可选 `source` 用于消歧义。
  - 对歧义场景系统 MUST 报错并提示补充 `source` 或改用 alias/`field_id`。

显式条目的覆写项为除选择器键之外的其它键，用于覆写字段定义（例如 `name`/`relation`/`value_cast` 等）。

schema 的 `description`/`markdownDescription`/示例 MUST 展示 alias 复用与显式选择器的用法，并明确说明 YAML merge（`<<`）会丢失对象身份，merge 产物需要选择器键才能解析。

#### Scenario: output.fields 解析支持显式选择器
- **WHEN** `output.fields` 包含显式 `field_id` 对象或 `{field: <data_key>, source?: ...}` 选择器
- **THEN** 解析器 MUST 正确解析并应用覆写

#### Scenario: output.fields 拒绝字符串与 merge 产物
- **WHEN** `output.fields` 包含字符串或 merge 产物（缺少选择器键）
- **THEN** 校验必须失败并提示改用显式对象条目

### Requirement: 字段 ID 唯一性与解析规则

系统 SHALL 要求源字段 `field_id` 在单个 source 内唯一；派生字段 `field_id` 全局唯一且不得与任何源字段同名。
系统 SHALL 允许源字段 `field_id` 采用 `<source_id>.<field_id>` 命名约定并视为普通字符串；同一 source 内多个字段可引用相同 `data_key`（例如多个字段的 `extract` 为同一个顶层 key），但 `field_id` 不同。
当 `output.fields` 缺省且存在跨 source 同名 `field_id` 时，校验必须失败并提示必须显式指定 `output.fields`。

#### Scenario: 派生/源同名 field_id
- **WHEN** 顶层 `fields` 与 `main_source.fields`/`sources.*.fields` 使用相同 `field_id`
- **THEN** 校验必须失败并提示派生/源同名不允许

### Requirement: 派生字段支持 call_by Schema

Schema 生成器 SHALL 在派生字段定义中加入 `call_by` 字段，类型为字符串，并在 schema hover 中说明 `reference(args...)` 语法、kwargs 示例、Python 字面量示例与 `$ctx.*` 可用属性。
schema hover MUST 明确 `reference` 的 module path 同时支持绝对引用与相对引用（以 `.` / `..` 开头，相对 YAML 文件所在目录）。
Schema SHALL 对派生字段声明 `compute` 与 `call_by` 做互斥约束（oneOf），并确保源字段/主源字段不允许出现 `call_by`。

#### Scenario: call_by 仅允许派生字段且与 compute 互斥
- **WHEN** 源字段中出现 `call_by` 或同一派生字段同时声明 `compute` 与 `call_by`
- **THEN** schema 校验失败并提示约束错误

#### Scenario: call_by 语法说明可见且包含相对引用
- **WHEN** 在 LSP/Schema hover 查看 `call_by`
- **THEN** 显示函数引用格式、kwargs 示例与 `$ctx.*` 可用属性说明
- **AND** hover MUST 包含至少一个相对引用示例

### Requirement: schema meta key 参考文档与推荐写法

系统 MUST 提供一份可发现的 schema meta key 参考，用于约束与指导 `_schema_meta(...)` 的使用。
该参考 MUST 至少包含：
- 支持的 shorthand keys/别名与其对应的 JSONSchema 字段
- 推荐的 canonical 写法
- 可复制的示例（至少覆盖常见 meta key）

#### Scenario: 新同事查阅 schema meta key
- **WHEN** 用户需要为 YAML DSL schema 增加 hover 描述/枚举/示例并使用 `_schema_meta(...)`
- **THEN** 系统应提供一份集中参考，列出可用 key 与推荐写法，并包含可复制示例

### Requirement: schema meta 中 schema dict 不得吞掉 desc/md

系统 MUST 在生成 YAML DSL JSON Schema 时保留 `_schema_meta(...)` 中除 `schema` 之外的 meta 信息（例如 `desc`/`md`/`examples` 等），以避免 LSP hover 缺失。

#### Scenario: main_source.order_by hover 可见
- **WHEN** 生成 demand JSON Schema
- **THEN** `definitions.main_source.properties.order_by` MUST 包含 `description` 或 `markdownDescription`（至少其一）以支持编辑器 hover

### Requirement: schema 明确 batch_size 的 null-or-int 语义

Schema 生成器 MUST 将顶层 `batch_size` 定义为 `oneOf`：
- `type: "null"`（语义：禁用分批）
- `type: "integer"` 且 `minimum: 1`（语义：固定分批）

schema hover/markdownDescription MUST 明确区分三种状态：
- 未声明：沿用默认分批策略。
- 显式 `null`：no-chunking（单批执行）。
- 显式整数：按固定批大小分批。

#### Scenario: schema batch_size 校验
- **WHEN** 配置 `batch_size` 为合法值（null 或正整数）或非法值（0、负数、浮点数、布尔值、非数字字符串）
- **THEN** schema 校验 MUST 按预期通过或失败

### Requirement: retry 字段纳入 JSON Schema 与 hover 指引

系统 SHALL 在生成的 YAML DSL JSON Schema 中新增 retry 字段支持：
- 顶层可选对象 `retry`
- `main_source` 下的可选对象 `retry`
- `sources.*` 下的可选对象 `retry`
- `_templates.retry` 对象映射（template_name -> retry policy 对象）

Schema MUST 为 retry policy 字段提供：
- 类型约束（bool/int/number/enum）
- 范围约束（至少包含硬上限）
- 简短 hover 指引，说明安全默认值与"默认不启用"的语义

约束：
- `_templates` 的其它内容保持 freeform（不要求 schema 穷举/校验），但 `_templates.retry.*` MUST 按 retry policy 规则校验
- `retry.should_retry` MUST 为非空字符串（当显式提供时）

#### Scenario: retry schema 校验
- **WHEN** retry 配置缺失、包含非法枚举值或超过硬上限
- **THEN** schema 校验 MUST 按预期通过或失败并指出错误

### Requirement: schema 说明源代码级 `normalize` 及其执行顺序

系统 MUST 在 YAML DSL JSON Schema 的 `sources.*` 定义中新增 `normalize` 字段，并在 `description` / `markdownDescription` 中明确说明：
- `normalize` 是源代码级整体结果归一化
- `normalize` 先于字段级 `extract` 执行
- `normalize.kind=index_by_key` 的输入输出形状示例

约束：
- `main_source` MUST NOT 暴露 `normalize` 字段
- `sources.*.normalize.on_none` MUST 为 `raise|skip`
- 仅当 `sources.*.normalize.kind=index_by_key` 时允许出现 `on_none`
- 当 `sources.*.normalize.kind` 为其它值且出现 `on_none` 时，系统 MUST 拒绝该配置

#### Scenario: schema hover 包含 normalize 说明
- **WHEN** 生成 demand JSON Schema
- **THEN** `sources.*.normalize` 的文案 MUST 展示形状示例
- **AND** MUST 明确说明该能力不是字段级提取

#### Scenario: normalize 约束校验
- **WHEN** `main_source` 包含 `normalize` 或非 `index_by_key` 的 normalize kind 包含 `on_none`
- **THEN** schema/运行时校验 MUST 失败并指出错误

### Requirement: `outputs.*.fields` 支持 YAML alias 与 object 条目

系统 MUST 允许 `outputs[*].fields` 的每一项为以下两种之一：
- `field_id` 字符串（已弃用，推荐使用显式对象）
- YAML alias（object）条目：条目为某个"已定义字段对象"的 alias（展开后为 dict），系统 MUST 将其解析为该字段对象对应的 `field_id`

字段对象的来源包括：
- `main_source.fields.*`
- `sources.*.fields.*`
- 顶层派生字段 `fields.*`

schema MUST 在生成的 YAML DSL JSON Schema 中允许 `outputs[*].fields.items` 为 `string | object`，以避免 schema-only 校验与编辑器提示拦截 alias 写法。

当 object 条目无法通过"对象身份"（identity）反查到字段对象时，系统 SHALL 允许基于内容相等做兜底匹配，但仅当匹配结果唯一时才允许成功解析。

#### Scenario: outputs.fields 使用 alias 解析
- **GIVEN** 字段对象已定义
- **WHEN** `outputs[0].fields` 包含该字段的 alias
- **THEN** 校验 MUST 通过且解析后的 `outputs[0].fields` MUST 包含对应 `field_id`

#### Scenario: alias identity 失败时 content match 兜底
- **GIVEN** `outputs[0].fields[*]` 无法通过对象身份反查
- **WHEN** 系统尝试基于内容相等匹配
- **THEN** 唯一匹配 MUST 成功，歧义或找不到 MUST fail-fast 并提示

#### Scenario: schema validate 不因 object 条目直接失败
- **GIVEN** `outputs[0].fields` 包含 YAML alias（object）条目
- **WHEN** 执行 schema-only 校验
- **THEN** 校验 MUST NOT 因 `outputs[0].fields[*]` 的类型为 object 而失败

### Requirement: schema MUST support `{$init_var: <name>}` for resource paths

系统 MUST 在 YAML DSL JSON Schema 中对资源路径字段支持 `{$init_var: <name>}` 指令节点注入输出路径（对象节点，不是字符串插值）：

- 路径字段 MUST 支持非空静态字符串路径或 `{$init_var: <name>}` 指令节点
- 路径字段为空字符串 MUST 被拒绝

说明：
- `.xlsx` 输出路径注入通过 books 资源与 export_xlsx 路径字段。

#### Scenario: schema validate accepts string or init_var object for file paths
- **WHEN** 执行 demand schema-only 校验且文件路径使用静态字符串或 `{$init_var: <name>}` 语法
- **THEN** 校验 MUST 通过
- **AND** 空字符串路径 MUST 被拒绝

### Requirement: kind-based `if/then` constraints MUST NOT trigger when `kind` is missing

系统 MUST 生成 JSON schema，使得所有基于 `kind` 分支的 `if/then` 约束在 `kind` 缺失时不触发。

动机：
- 编辑器侧的 YAML schema 校验不会展开 `$import`，因此允许存在 `{ $import: ... }` 形态的 mapping（此时 `kind` 通常在 fragment 内声明）。
- JSON schema 的 `properties.kind.const` 在 `kind` 缺失时不会失败，若不额外约束会导致 `then` 被错误触发，产生假阳性。

约束：
- 当 `if` 用于匹配 `properties.kind.const`（或等价模式）时，`if` MUST 同时包含 `required: ["kind"]`。
- 此要求 MUST 覆盖所有使用 kind-variant 生成模式的定义。

#### Scenario: schema validates `$import`-based mapping without false positives
- **GIVEN** demand YAML 中资源使用 `{ $import: <fragment> }` 且 fragment 内声明 `kind`
- **WHEN** VSCode YAML schema（不展开 `$import`）对主 YAML 进行校验
- **THEN** MUST NOT 报告假阳性错误

### Requirement: schema MUST NOT expose runtime policy fields

某些字段属于 runtime policy（可能包含敏感信息或仅为运行时配置），系统 MUST 不将其作为 demand YAML stable authoring 字段暴露在 schema 中。

包括但不限于：
- `include_full_error_message`

#### Scenario: schema no longer exposes runtime policy fields
- **WHEN** 生成 demand JSON Schema
- **THEN** schema MUST NOT 暴露 runtime policy 专用字段
