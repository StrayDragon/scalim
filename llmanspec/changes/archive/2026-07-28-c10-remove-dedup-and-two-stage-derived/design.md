# Design — remove-dedup-and-two-stage-derived

## Decision

删除 Python-only 派生装配 `DedupBy*` / `TwoStageGroupBy*`（YAML 从未暴露）。保留 `DerivedGroupBySpec`、metrics（含 `count_distinct` / `count_true_gte`）、rank、post `compute`/`call_by`。

## Alternatives for callers

| 原能力 | 替代 |
|---|---|
| `DerivedDedupByGroupBySpec` | loader/上游去重，或接受重复行后只用 `DerivedGroupBySpec` |
| `TwoStageGroupBySpec` | workflow 两段 demand（中间表 → 再聚合） |

## Spec drift cleanup

cardinality 移除后 yaml-dsl specs 中「YAML `dedup_by.on_conflict` 保留」等表述与实现不符——本变更一并删除/改写。

## Test seams（pytest）

| Seam | 现有入口 |
|---|---|
| Aggregator / Spec API | `tests/yaml_dsl/test_derived_outputs.py`、`tests/execution/test_output_composition.py` |
| Demo package | `packages/scalim-misc/.../derived_set_aggregations_demo.py`、notebooks `ch120` |
| Live specs | `execution-derived-outputs` r755/r160/r199；`ir-key-normalization` dedup 场景 |

## Out of scope

- `count_true_gte` 保留
- BookBudget（`c0-remove-book-budget-policy`）
