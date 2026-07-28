# 2026-07-24: remove-derived-outputs-cardinality-guardrails

## 变更摘要

BREAKING：派生输出（derived outputs）的**基数护栏体系**整体移除。

| 面 | 移除项 |
|---|---|
| YAML `outputs.<name>.aggregate` | `max_groups` / `max_distinct` / `distinct_on_overflow` |
| Python IR `DerivedGroupBySpec` | 同上三构造参数 |
| Python IR `DedupBySpec` | `max_distinct` / `on_overflow`（当时保留 `on_conflict`；**整类 Dedup/TwoStage 已于 2026-07-28 移除**，见 `2026-07-28-remove-dedup-and-two-stage-derived.md`） |
| 策略枚举 | `DerivedOverflowPolicy` |
| 错误类 | `ScalimAggregationKeyLimitExceededError` / `ScalimDistinctKeyLimitExceededError` |
| 运行期行为 | 未设护栏时的 `scalim.derived_outputs` WARNING；meta/audit 的 `truncated` 截断审计 |

`count_distinct` 的 distinct 状态退化为无界 `set`。高基数聚合的内存风险交由宿主系统层（如 OOM killer）兜底；不再提供 `truncate` 降级路径。

指纹（`fingerprint_parts`）会少若干行——meta sheet 对拍值会变，属显式破坏。

对应 llmanspec change: `llmanspec/changes/archive/2026-07-24-c15-remove-derived-outputs-cardinality-guardrails/`

历史上下文（引入护栏的批次）: `2026-03-13-derived-outputs-set-aggregations.md`

## Migration Checklist

### 1) YAML：删除残留护栏字段

Before（现已 fail-fast）：

```yaml
outputs:
  by_region:
    aggregate:
      group_by: [region]
      max_groups: 10000
      max_distinct: 5000
      distinct_on_overflow: truncate
      fields:
        cnt: {count: {}}
```

After：

```yaml
outputs:
  by_region:
    aggregate:
      group_by: [region]
      fields:
        cnt: {count: {}}
```

### 2) Python IR：去掉构造参数

Before（现会 `TypeError`）：

```python
DerivedGroupBySpec(
    group_by=("region",),
    metrics=(...),
    max_groups=10000,
    max_distinct=5000,
    distinct_on_overflow=DerivedOverflowPolicy.TRUNCATE,
)
```

After：只保留业务语义字段（`group_by` / metrics / ranks / post fields 等）；不要再传护栏参数，也不要再 import `DerivedOverflowPolicy`。

（历史）`DedupBySpec` 同理曾删除 `max_distinct` / `on_overflow` 并保留 `on_conflict`；随后整类已移除，见 `2026-07-28-remove-dedup-and-two-stage-derived.md`。

### 3) 下游 try/except

若代码捕获 `ScalimAggregationKeyLimitExceededError` / `ScalimDistinctKeyLimitExceededError`，删除这些分支（类型已不存在）。高基数风险改由进程级资源限制 / 宿主监控处理。

## 常见报错与修复

- `aggregate.max_groups was removed` / `max_distinct was removed` / `distinct_on_overflow was removed`
  - 从 YAML `outputs.*.aggregate` 删除该字段
- `TypeError: ... unexpected keyword argument 'max_groups'`（或 `max_distinct` / `distinct_on_overflow` / `on_overflow`）
  - 从 Python IR 构造调用中删除对应 kwargs
