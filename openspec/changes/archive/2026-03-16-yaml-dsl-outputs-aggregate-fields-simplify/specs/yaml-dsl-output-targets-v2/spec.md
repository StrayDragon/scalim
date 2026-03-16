## ADDED Requirements

### Requirement: `outputs[*].where` is a row-level predicate for routing rows into a target
系统 MUST 支持在 `outputs[*]` 上声明 `where` 作为行级过滤谓词:
- 当 `where` 存在时,系统 MUST 对每行计算该谓词
- 仅当谓词为 true 时,该行才进入当前 output(明细输出或聚合输出)
- `where` MUST 使用安全表达式,并在编译期静态提取依赖字段并注入 required fields

#### Scenario: `where` 将行路由到不同 sheet
- **GIVEN** 同一份 demand 中存在两个 workbook sheet 输出,分别声明 `where: "no_promotion"` 与 `where: "has_promotion"`
- **WHEN** 系统运行该 demand
- **THEN** 系统 MUST 仅将满足各自 `where` 的行写入对应 sheet

### Requirement: `aggregate.fields` replaces `aggregate.metrics` and is field-centric
系统 MUST 将 `outputs[*].aggregate.metrics` 替换为 `outputs[*].aggregate.fields`(破坏性变更),并将其视为“聚合输出字段定义映射”.

#### Scenario: `aggregate.fields` 作为唯一聚合字段入口
- **WHEN** 用户在 `outputs[*].aggregate.fields` 中声明聚合指标字段
- **THEN** 系统 MUST 以该映射的 key 作为聚合输出的 `field_id`
- **AND** 系统 MUST NOT 再接受 `outputs[*].aggregate.metrics`

### Requirement: aggregate metric fields use "function key" form instead of `{op: ...}`
系统 MUST 支持在 `aggregate.fields.<field_id>` 中使用“函数当 key”的指标声明形态,并提供强 schema 补全.

系统 MUST 至少支持下列聚合函数 key:
- `count`
- `sum`
- `min`
- `max`
- `count_true`
- `count_true_gte`
- `count_distinct`

约束:
- 每个 `aggregate.fields.<field_id>` MUST 恰好包含一个“聚合函数 key”(不得同时出现多个)
- 对需要输入字段的函数,其参数 MUST 显式声明(例如 `sum.field`)

#### Scenario: `count` 指标的函数 key 写法
- **GIVEN** `aggregate.fields.order_cnt: {count: {}}`
- **WHEN** 系统解析并运行聚合输出
- **THEN** 系统 MUST 产生 `order_cnt` 输出字段且语义等价于旧写法 `order_cnt: {op: count}`

#### Scenario: `count_distinct` 支持单字段与复合字段
- **WHEN** 用户声明:
  ```yaml
  aggregate:
    fields:
      u_cnt: {count_distinct: {field: user_id}}
      u_item_cnt: {count_distinct: {fields: [user_id, item_id]}}
  ```
- **THEN** 系统 MUST 正确统计 distinct 且结果确定性

### Requirement: rank fields are expressed as fields with rank function keys
系统 MUST 支持在 `aggregate.fields.<field_id>` 中声明排名字段,并以 rank 函数 key 表达排名模式:
- `row_number`
- `rank`
- `dense_rank`

rank 字段配置 MUST 至少支持:
- `by`: 用于计算 rank 值与并列判断的字段(必须引用 `group_by` 字段或聚合指标字段)
- `partition_by`: 可选;必须是 `group_by` 子集;缺省表示全局
- `order`: `asc|desc`
- `order_by`: 可选;用于输出稳定排序与 `top_k_mode=rows` 的稳定 tie-break
- `top_k`: 可选;对 partition 生效
- `top_k_mode`: `rank|rows`

#### Scenario: `dense_rank` 同值同名次
- **GIVEN** 聚合输出行中 `metric_value` 为 `[10, 10, 8]`(同一 partition)
- **WHEN** 声明 `rank` 字段为 `dense_rank` 且 `by: metric_value` 且降序
- **THEN** 系统 MUST 输出 rank 为 `[1, 1, 2]`

#### Scenario: `partition_by` 重置分区内排名
- **GIVEN** 聚合输出包含两个分区 `group_id=G1/G2`,且每个分区各两行
- **WHEN** rank 字段声明 `partition_by: [group_id]`
- **THEN** 系统 MUST 在每个分区内将 rank 从 1 开始重新计数

### Requirement: `top_k_mode` default preserves ties per partition
系统 MUST 定义 `top_k` 在 partition 场景的默认语义为“含并列扩张”:
- 当 `top_k_mode=rank`(默认)时,系统 MUST 保留 `rank_value <= K` 的所有行(含并列扩张)
- 当 `top_k_mode=rows` 时,系统 MUST 每个分区强行保留前 K 行(允许截断并列),并要求 `order_by` 提供稳定 tie-break

#### Scenario: `top_k_mode=rank` 含并列扩张
- **GIVEN** 某分区内存在三行,其 `by` 值为 `[10, 10, 8]`
- **WHEN** `top_k=1` 且 `top_k_mode=rank`
- **THEN** 系统 MUST 保留两条 `by=10` 的行(并列扩张)

#### Scenario: `top_k_mode=rows` 强行取 K 行且要求 `order_by`
- **WHEN** `top_k=1` 且 `top_k_mode=rows` 且未提供 `order_by`
- **THEN** 系统 MUST fail-fast 并提示必须提供 `order_by` 以保证确定性

### Requirement: `aggregate.fields.<field_id>.call_by` provides a hotfix escape hatch
系统 MUST 支持在 `aggregate.fields.<field_id>` 中声明 `call_by` 作为聚合后派生字段的 hotfix 口子:
- `call_by` MUST 受 allowlist(allowed_modules/allowed_functions)约束
- `call_by` MUST 在聚合与 rank finalize 后执行

#### Scenario: `call_by` 基于 rank 计算 score
- **GIVEN** 聚合输出包含字段 `rank`
- **WHEN** 用户声明 `score` 字段为 `call_by` 且其依赖 `rank`
- **THEN** 系统 MUST 在同一次 run 内输出 `score` 且不需要 workflow+中间文件
