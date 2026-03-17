## Context

下游 Excel 报表存在强“输出合同”约束(固定列顺序、重复/分段表头、对拍旧实现)。当前 YAML DSL 在 `outputs.*.aggregate` 场景存在限制:

- aggregate output 被视为 derived output,编译期禁止 `outputs.*.fields`,导致无法在 YAML 中声明 derived output 的列顺序。
- derived output 的字段缺少对显示名(包含重复表头)的一等支持。

此外,为了降低 YAML author 的心智负担与复用成本,需要在 `outputs.*.aggregate` 的字段引用位置支持 YAML alias:

- 支持 alias 引用 `main_source.fields` / `sources.*.fields` / 顶层 `fields` 的字段定义对象,并解析为对应 `field_id`。
- 支持 alias 引用 `outputs.*.aggregate.fields.<out_field_id>` 的字段定义对象,并解析为对应的 `out_field_id`(用于 rank/score_by_rank 等聚合内引用位置)。

约束:

- `src/scalim/` 运行时必须兼容 Python 3.6。
- schema/hover 需要覆盖新写法,避免 LSP 报错误导作者。
- drift gate: `just qa` 会运行 `just openspec-check` + pytest + lint,变更需补齐 spec 并用测试兜底。

## Goals / Non-Goals

**Goals:**

- aggregate output 允许声明 `outputs.*.fields`,用于输出编排(select + order),不改变聚合计算语义。
- `aggregate.fields.<out_field_id>` 支持可选显示名 `name`,在 `header_fields_output_by: name` 时输出该 name 作为表头,并允许重复。
- 在 `outputs.*.aggregate` 内的所有输入字段引用位置支持 YAML alias(字段定义对象/list),并保持与 `outputs.*.fields` 一致的解析行为。
- 在 `outputs.*.aggregate` 内的聚合输出字段引用位置(例如 `rank.by`/`order_by`/`score_by_rank.rank_field`)支持 YAML alias(聚合字段定义对象),提升复用性。

**Non-Goals:**

- 不引入新的 DSL 结构(例如 `aggregate_fields:` 平铺或根级 `aggregates:`)。
- 不调整 aggregate 的执行阶段顺序(指标 → rank → post)或放开 GAP1-3 的能力边界。
- 不对 YAML 作者的“声明顺序”做合同承诺(省略 `outputs.*.fields` 时的默认顺序仅为实现细节)。

## Decisions

1) **统一字段引用解析:**

- 对于期望 `field_id` 的位置,允许两种等价写法:
  - 直接 `field_id` 字符串
  - YAML alias 引用字段定义对象(来源: `main_source.fields` / `sources.*.fields` / 顶层 `fields`)
- 对于期望聚合输出字段 ID(`out_field_id`)的位置,允许:
  - 直接 `out_field_id` 字符串
  - YAML alias 引用 `aggregate.fields.<out_field_id>` 对应的字段定义对象(要求可唯一解析)
- list 场景支持 YAML alias(list) 产生的嵌套 list,通过 parse 期 flatten 处理,行为与 `outputs.*.fields` 对齐。

2) **显式输出布局优先级:**

- 若 aggregate output 声明了 `outputs.*.fields`,则 derived output layout MUST 使用该字段顺序(select + order)。
- 若省略 `outputs.*.fields`,则使用默认 derived layout(实现为稳定顺序但不承诺为合同)。

3) **表头 name 的来源:**

- 当 `header_fields_output_by: name`:
  - 对输入字段(普通 fields)仍使用 demand IR 的 field name 规则。
  - 对聚合输出字段优先使用 `aggregate.fields.<out_field_id>.name`,否则回退为 `out_field_id`。
- 允许多个字段输出相同表头文本,以满足重复表头合同。

## Risks / Trade-offs

- [schema 放宽导致误通过] 允许 object 类型会降低 JSON schema 对错误配置的捕获能力 → 通过 parse 期语义校验 + pytest 覆盖关键路径。
- [alias identity 丢失] YAML merge(`<<`) 可能产生新对象导致 alias identity 丢失 → 维持“按内容唯一匹配”的兜底策略,并在 hover 文本中建议作者优先使用字符串 `field_id`。
- [默认顺序争议] 省略 `outputs.*.fields` 的默认列顺序可能被误认为合同 → 在 hover/文档中明确“不保证顺序,强合同请显式声明 fields”。

