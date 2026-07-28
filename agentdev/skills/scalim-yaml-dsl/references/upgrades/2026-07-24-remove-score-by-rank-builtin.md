# 2026-07-24: remove-score-by-rank-builtin

## 变更摘要

BREAKING：移除聚合后置派生字段内置 `score_by_rank`（`score = base - (rank - 1) * step`）。

等价能力已由通用 `compute` 表达式覆盖；`AGG_POST_PRODUCER_KEYS` 现仅保留 `call_by` / `compute`。

残留 YAML `score_by_rank` 在解析期 **fail-fast**，并提示迁移为 `compute`。

对应 llmanspec change: `llmanspec/changes/archive/2026-07-24-c0-remove-score-by-rank-builtin/`

历史上下文（aggregate.fields / post fields）: `2026-03-16-yaml-dsl-outputs-aggregate-fields.md`

## Migration Checklist

### 1) YAML：`score_by_rank` → `compute`

Before（现已 fail-fast）：

```yaml
fields:
  rank:
    dense_rank:
      order_by: [{field: sum_amount, order: desc}]
  score:
    score_by_rank: {rank_field: rank, base: 100, step: 3}
```

After：

```yaml
fields:
  rank:
    dense_rank:
      order_by: [{field: sum_amount, order: desc}]
  score:
    compute: "100 - (rank - 1) * 3"
```

公式：`base - (rank - 1) * step`（把字面量代入 `compute` 字符串即可）。

### 2) 示例 / 回归

仓库内权威示例：`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_rank_score_report.yaml`（已迁到 `compute`）。

## 常见报错与修复

- `has removed 'score_by_rank'; please replace with 'compute' expression`
  - 按上面把 `score_by_rank: {rank_field, base, step}` 换成 `compute: "<base> - (rank - 1) * <step>"`（`rank` 换成你的排名字段 id）
