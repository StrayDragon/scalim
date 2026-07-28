# 2026-03-13: derived-outputs-set-aggregations

本组变更为 `derived-outputs` 补齐常见 set 口径聚合原语,用于减少业务侧 Python state,并为后续 YAML outputs/workbook 编排面打底。

## 关联工件

- change 归档目录: `llmanspec/changes/archive/2026-03-13-derived-outputs-set-aggregations/`
- 主规范: `llmanspec/specs/execution-derived-outputs/spec.md`

## 变更摘要(IR/Python-only)（历史引入）

- 新增内置 metric op:
  - `count_distinct`(支持单字段与复合 key; `None` 按 SQL `COUNT(DISTINCT)` 语义忽略)
  - `count_true_gte(field_id, threshold)`(用于最小条件计数,覆盖 `repeat_paid_users`)
- 扩展派生聚合装配 spec(用于 `output_composition.derived_targets`):
  - `DerivedGroupBySpec` 新增 `max_distinct` 与 `distinct_on_overflow=error|truncate`
  - ~~新增 `DedupBySpec` + `DerivedDedupByGroupBySpec`~~（后续已移除，见下）
  - ~~新增 `TwoStageGroupBySpec`(stage1 finalize → stage2 accumulate)~~（后续已移除，见下）
- `parallel_mode="adaptive"` 一致性边界（历史）:
  - 当时 `dedup_by.on_conflict=first|last` 属于顺序依赖语义,在 `adaptive` 下会 fail-fast
- 诊断输出:
  - meta sheet 写入 `derived.<target_id>.fingerprint` 等对拍友好的稳定诊断字段
  - audit sheet 会额外记录截断等结构化审计行(不包含明细/聚合 key 具体值)

> ⚠️ 已被后续变更移除(2026-07-24, `c15-remove-derived-outputs-cardinality-guardrails`):
> 上述 `max_groups` / `max_distinct` / `distinct_on_overflow` / `dedup_by.on_overflow` 基数护栏体系已整体移除。
> `count_distinct` 的 distinct 状态退化为无界 `set`;高基数聚合的内存风险交由宿主系统层(如 `OOM` killer)兜底。
> meta/audit 中的 `truncated` 标记与截断审计行也不再产生。
>
> **迁移 SSOT**: `2026-07-24-remove-derived-outputs-cardinality-guardrails.md`

> ⚠️ 已被后续变更移除(2026-07-28, `c10-remove-dedup-and-two-stage-derived`):
> `DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec` 及 `DedupOnConflictPolicy` / `ScalimDedupKeyConflictError` 整类删除。
> YAML 从未暴露这些字段；Python 调用方改走 loader/上游去重，或 workflow 两段 demand。
>
> **迁移 SSOT**: `2026-07-28-remove-dedup-and-two-stage-derived.md`

## 升级建议（现行）

- 若你仅使用基础 `group_by` + `count/sum/min/max/count_true` / `count_distinct` / `count_true_gte` / rank / post `compute`/`call_by`,不需要因本批次改动。
- 基数护栏已移除: 详见 `2026-07-24-remove-derived-outputs-cardinality-guardrails.md`;残留字段会在解析期 `fail-fast`。
- 若历史代码仍引用 `DedupBy*` / `TwoStageGroupBy*`: 详见 `2026-07-28-remove-dedup-and-two-stage-derived.md`。
