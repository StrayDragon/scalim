## ADDED Requirements

### Requirement: schema hover for `outputs[*].where` explains stage, scope, and variable origin
系统 MUST 在 schema 的 `outputs[*].where` hover 文案中尽可能详细地解释其语义与可用变量来源,至少包含:
- `where` 为**行级过滤谓词**(按行路由/过滤),等价 SQL `WHERE`
- 执行阶段:
  - 对明细输出: 写出前对每行执行
  - 对聚合输出: `group_by` 之前对每行执行(只有命中的行参与聚合)
- 表达式可引用的变量来自当前行的字段值: demand 中的 `fields.<field_id>`(包含 relation/derive 后字段)
  - 系统会在编译期静态提取表达式依赖字段并注入 required fields
  - 只保证表达式引用到的字段会被准备;未引用字段可能为 `None`
- `where` MUST NOT 被解释为“是否启用 sheet/output”的开关;该能力应由未来独立字段提供(例如 `enabled_if`)

#### Scenario: `where` hover 文案包含行级说明
- **WHEN** 生成 YAML DSL JSON Schema
- **THEN** `outputs.items.properties.where.markdownDescription` MUST 提及“行级过滤/按行”
- **AND** MUST 提及“聚合前/group_by 之前”的执行阶段
- **AND** MUST 提及“变量来自 fields.<field_id> / 当前行字段值”

## RENAMED Requirements

### Requirement: derived aggregate metric map is renamed from `metrics` to `fields`
FROM: `outputs[*].aggregate.metrics`  
TO: `outputs[*].aggregate.fields`

#### Scenario: schema exposes `aggregate.fields` and rejects `aggregate.metrics`
- **WHEN** 生成 YAML DSL JSON Schema
- **THEN** schema MUST 包含 `outputs.items.properties.aggregate.properties.fields`
- **AND** schema MUST NOT 包含 `outputs.items.properties.aggregate.properties.metrics`

## ADDED Requirements

### Requirement: schema hover for `aggregate.group_by` explains grouping semantics and origin
系统 MUST 在 schema 的 `outputs[*].aggregate.group_by` hover 文案中解释,至少包含:
- `group_by` 引用的是输入行字段(`field_id`),来自 `where` 过滤后的行流
- 每个唯一的 group key 组合会产生 1 行聚合输出
- `partition_by`(排名分区)约束为 `group_by` 子集的原因(分区键必须可在聚合输出中直接解释)

#### Scenario: `group_by` hover 文案包含来源说明
- **WHEN** 生成 YAML DSL JSON Schema
- **THEN** `outputs.items.properties.aggregate.properties.group_by.markdownDescription` MUST 提及“来自 where 过滤后的行”

### Requirement: schema hover for `aggregate.fields` explains producer keys and evaluation order
系统 MUST 在 schema 的 `outputs[*].aggregate.fields` hover 文案中解释,至少包含:
- map key 是聚合输出字段 ID
- 每个字段 value MUST 选择且仅选择一个 producer key(聚合函数 / 排名函数 / call_by 派生)
- 执行顺序: 先聚合指标 → 再排名字段 → 再聚合后派生字段
- 聚合后派生字段可引用的字段范围(至少说明“可引用 group_by/聚合指标/排名字段,不可引用明细行未保留的中间状态”)

#### Scenario: `aggregate.fields` hover 文案包含执行顺序
- **WHEN** 生成 YAML DSL JSON Schema
- **THEN** `outputs.items.properties.aggregate.properties.fields.markdownDescription` MUST 提及“执行顺序”

### Requirement: schema provides strong completion for aggregate metric "function key" form
系统 MUST 在生成的 YAML DSL JSON Schema 中为 `outputs[*].aggregate.fields.<field_id>` 提供“函数当 key”的强补全与约束:
- MUST 至少支持 `count/sum/min/max/count_true/count_true_gte/count_distinct`
- MUST 约束每个字段对象恰好匹配一个函数 key 形态(避免多 key 并存导致歧义)

#### Scenario: schema-only 校验允许 `count` 函数 key
- **WHEN** YAML 包含:
  ```yaml
  outputs:
    - name: by_region
      container: {type: csv, path: ./out.csv}
      aggregate:
        group_by: [region]
        fields:
          order_cnt: {count: {}}
  ```
- **THEN** schema-only 校验 MUST 通过(编辑器提示应能补全 `count`)

### Requirement: schema hover describes each function key and its parameters
系统 MUST 在 schema 的 hover 文案中为每个允许的 producer key 提供可读的语义说明与参数说明(至少覆盖聚合函数与排名函数):
- 聚合函数 keys: `count/sum/min/max/count_true/count_true_gte/count_distinct`
- 排名函数 keys: `row_number/rank/dense_rank`
- `call_by` hotfix key: 说明其为聚合后派生字段,执行在聚合+排名之后,且受 allowlist 约束

建议 hover 至少包含:
- 返回值含义(例如 count 为行数, sum 为数值求和)
- 参数含义(例如 `sum.field` 指定输入字段; `count_distinct.fields` 为复合去重键; `count_true_gte.threshold` 为阈值)
- 常见误用提示(例如 `top_k_mode=rows` 需要稳定 `order_by`)

#### Scenario: schema hover 为 producer key 提供语义说明
- **WHEN** 生成 YAML DSL JSON Schema
- **THEN** schema MUST 为至少一个聚合函数 key(例如 `sum`)提供 `markdownDescription` 且包含其语义与参数说明
- **AND** schema MUST 为至少一个排名函数 key(例如 `dense_rank`)提供 `markdownDescription` 且包含其语义说明(并列处理)
