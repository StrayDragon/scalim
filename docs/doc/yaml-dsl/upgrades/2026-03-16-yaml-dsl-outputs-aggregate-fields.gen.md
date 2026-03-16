<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- artifacts/skills/scalim-yaml-dsl/references/upgrades/2026-03-16-yaml-dsl-outputs-aggregate-fields.md
-->
# 2026-03-16: yaml-dsl-outputs-aggregate-fields

## 变更摘要

本批次重做 `outputs.*.aggregate` 的最小语法,让“最终输出字段(field_id)”成为主体,并补齐 finalize 排名/派生字段能力:

- `outputs.*.where` 字段名不变(语义不变),但 editor hover 文案会明确其为 **行级过滤谓词**(不是 sheet enable 开关)
- **BREAKING**: `outputs.*.aggregate.metrics` → `outputs.*.aggregate.fields`(不做兼容别名,一次性升级)
- **BREAKING**: `aggregate.fields.<out_field_id>` 使用“函数当 key”的写法,替代旧 `{op: ...}` 映射
- **NEW**: `aggregate.fields` 同时支持:
  - 排名字段: `row_number` / `rank` / `dense_rank`(支持 `partition_by` / `order_by` / `top_k_mode`)
  - 聚合后派生字段: `score_by_rank`(内置) 与 `call_by`(hotfix 口子,受 allowlist 约束)

OpenSpec 工件:
- `openspec/changes/yaml-dsl-outputs-aggregate-fields-simplify/`

## BREAKING: `aggregate.metrics` → `aggregate.fields`

旧写法:

```yaml
aggregate:
  group_by: [channel]
  metrics:
    order_cnt: {op: count}
    sum_amount: {op: sum, field: amount_yuan}
```

新写法:

```yaml
aggregate:
  group_by: [channel]
  fields:
    order_cnt: {count: {}}
    sum_amount: {sum: {field: amount_yuan}}
```

## BREAKING: 指标条目从 `{op: ...}` 改为“函数当 key”

机械替换规则:

- `x: {op: count}` → `x: {count: {}}`
- `x: {op: count, field: some_id}` → `x: {count: {field: some_id}}`
- `x: {op: sum, field: amount}` → `x: {sum: {field: amount}}`
- `x: {op: min, field: amount}` → `x: {min: {field: amount}}`
- `x: {op: max, field: amount}` → `x: {max: {field: amount}}`
- `x: {op: count_true, field: flag}` → `x: {count_true: {field: flag}}`
- `x: {op: count_true_gte, field: amount, threshold: 100}` → `x: {count_true_gte: {field: amount, threshold: 100}}`
- `x: {op: count_distinct, field: user_id}` → `x: {count_distinct: {field: user_id}}`
- `x: {op: count_distinct, fields: [user_id, item_id]}` → `x: {count_distinct: {fields: [user_id, item_id]}}`

约束(更严格,更易于补全与 fail-fast):

- `aggregate.fields.<out_field_id>` 必须是 object 且必须且只能包含 **一个** producer key

## NEW: 排名字段(rank fields)

在同一 `aggregate.fields` 中声明排名字段:

```yaml
aggregate:
  group_by: [customer_id]
  fields:
    order_cnt: {count: {}}
    sum_amount: {sum: {field: amount_yuan}}
    rank:
      dense_rank:
        by: sum_amount
        order: desc
        top_k: 100
        top_k_mode: rank
```

常见校验规则(遇到报错时按此排查):

- `by` 必须引用 `group_by` 字段或聚合指标字段(例如 `sum_amount`)
- `partition_by` 必须是 `group_by` 的子集
- `top_k_mode: rows` 时必须提供 `order_by` 以保证确定性

## NEW: 聚合后派生字段(post fields)

### 1) `score_by_rank`(内置,强补全)

```yaml
score:
  score_by_rank:
    rank_field: rank
    base: 100
    step: 10
```

### 2) `call_by`(hotfix 口子,弱补全但受 allowlist 约束)

```yaml
score2: {call_by: "pkg.mod:score_from_rank(rank=rank, base=100, step=10)"}
```

限制:

- 执行顺序: 聚合指标 → 排名字段 → `call_by`
- 只能引用聚合输出行内字段(概念上: `group_by`/聚合指标/排名字段),不能引用明细行中间状态

## 常见报错与修复

- `aggregate.metrics was removed; use aggregate.fields`
  - 把 `metrics:` 改成 `fields:`
- `aggregate.fields.<id> must contain exactly 1 producer key`
  - 每个字段对象只能保留一个函数 key(例如只能是 `sum` 或 `dense_rank` 或 `call_by`)
- `top_k_mode='rows' requires order_by`
  - 增加 `order_by: [..]`(并确保字段可在聚合输出中引用)
- `partition_by must be a subset of group_by`
  - 只保留 `group_by` 内的分区键
- `call_by reference unknown fields`
  - `call_by(...)` 里只能引用 `group_by`/指标/排名字段(例如 `rank`/`sum_amount`)

## (可选) 脚本化升级入口(不承诺保留注释/anchors)

仓库内提供最小“机械替换器”脚本(会使用 `PyYAML safe_load/safe_dump`,因此不会保留注释/anchors):

```bash
python scripts/upgrade-yaml-dsl-aggregate-fields.py path/to/file.yaml --in-place
```

