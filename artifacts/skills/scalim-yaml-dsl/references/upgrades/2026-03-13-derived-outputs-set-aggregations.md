# 2026-03-13: derived-outputs-set-aggregations

本组变更为 `derived-outputs` 补齐常见 set 口径聚合原语,用于减少业务侧 Python state,并为后续 YAML outputs/workbook 编排面打底。

## 关联工件

- change 归档目录: `openspec/changes/archive/2026-03-13-derived-outputs-set-aggregations/`
- 主规范: `openspec/specs/derived-outputs/spec.md`

## 变更摘要(IR/Python-only)

- 新增内置 metric op:
  - `count_distinct`(支持单字段与复合 key; `None` 按 SQL `COUNT(DISTINCT)` 语义忽略)
  - `count_true_gte(field_id, threshold)`(用于最小条件计数,覆盖 `repeat_paid_users`)
- 扩展派生聚合装配 spec(用于 `output_composition.derived_targets`):
  - `DerivedGroupBySpec` 新增 `max_distinct` 与 `distinct_on_overflow=error|truncate`
  - 新增 `DedupBySpec` + `DerivedDedupByGroupBySpec`
  - 新增 `TwoStageGroupBySpec`(stage1 finalize → stage2 accumulate)
- `parallel_mode="adaptive"` 一致性边界:
  - `dedup_by.on_conflict=first|last` 属于顺序依赖语义,在 `adaptive` 下会 fail-fast(建议切 `seq` 或改 `on_conflict=error`)
- 诊断输出:
  - meta sheet 写入 `derived.<target_id>.fingerprint` 等对拍友好的稳定诊断字段
  - audit sheet 会额外记录截断等结构化审计行(不包含明细/聚合 key 具体值)

## 升级建议

- 若你仅使用基础 `group_by` + `count/sum/min/max/count_true`,不需要改动。
- 若需要 distinct/去重/两阶段口径:
  - 优先设置合理的 `max_distinct` 与 `distinct_on_overflow`/`on_overflow`
  - 若必须使用 `first/last`,确保运行在 `parallel_mode="seq"` 以保持确定性与可对拍。
