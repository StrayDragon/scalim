# 2026-07-28: remove-dedup-and-two-stage-derived

## 变更摘要

BREAKING：移除派生输出上的 Python-only 装配原语 `dedup_by` / `two_stage_group_by`（YAML 主线从未暴露）。

| 面 | 移除项 |
|---|---|
| Python IR | `DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec` |
| 运行期 | `DedupByThenAggregator` / `TwoStageGroupByAggregator` / `ScalimDedupKeyConflictError` |
| 策略枚举 | `DedupOnConflictPolicy` |
| 指纹 kind | `dedup_by` / `dedup_by+group_by` / `two_stage_group_by` 不再出现 |

**保留**：`DerivedGroupBySpec` + metrics（含 `count_distinct` / `count_true` / `count_true_gte`）、rank、post `compute`/`call_by`。

对应 change：`llmanspec/changes/archive/2026-07-28-c10-remove-dedup-and-two-stage-derived/`

历史上下文：`2026-03-13-derived-outputs-set-aggregations.md`（引入）；`2026-07-24-remove-derived-outputs-cardinality-guardrails.md`（曾收窄 `DedupBySpec` 护栏字段，本批次整类删除）。

## Migration Checklist

### 1) Python：删除 DedupBy / TwoStage 装配

Before：

```python
from scalim.execution.output_composition import (
    DedupBySpec,
    DerivedDedupByGroupBySpec,
    DerivedGroupBySpec,
    TwoStageGroupBySpec,
)

DerivedDedupByGroupBySpec(
    dedup_by=DedupBySpec(key_fields=("user_id",), on_conflict="first"),
    group_by=DerivedGroupBySpec(group_by=("cs_id",), metrics=(...)),
)

TwoStageGroupBySpec(stage1=..., stage2=...)
```

After：

- **去重再聚合**：在 loader / 上游先按业务 key 去重，再只用 `DerivedGroupBySpec`；或接受重复行后直接 `group_by`（视口径而定）。
- **两阶段聚合**：拆成 workflow 两个 demand/run——stage1 写出中间表 → stage2 再聚合。

### 2) 下游 try/except

若代码捕获 `ScalimDedupKeyConflictError`，删除这些分支（类型已不存在）。

### 3) YAML

无直接破坏（本未暴露 `dedup_by`）。文档/capability-matrix 中「Python-only dedup/两阶段」表述改为「已移除」。

## 常见报错与修复

- `ImportError` / `AttributeError` 涉及 `DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec` / `ScalimDedupKeyConflictError`
  - 按上表迁移到 loader 去重或两段 demand；删除相关 import
- `TypeError: ... unexpected keyword argument` 涉及已删构造参数
  - 停止构造上述 Spec；改用 `DerivedGroupBySpec` 或 workflow 两段聚合
