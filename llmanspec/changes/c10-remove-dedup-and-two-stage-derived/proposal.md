---
depends_on: []
---

## Why

`DedupBySpec` / `DerivedDedupByGroupBySpec` / `TwoStageGroupBySpec` 是派生输出上的 **Python-only 装配能力**（YAML DSL **零引用**），用于「先按 key 去重再聚合」与「两阶段 group_by」。

维护成本与使用量不成比例：

| 指标 | 数据 |
|---|---|
| YAML 暴露 | 无（`src/scalim/dsl/yaml_dsl` 无 `dedup`/`two_stage`） |
| 仓库用法 | IR demo `ch120` + `scalim-misc` `derived_set_aggregations_demo` |
| 已知下游 | 0 |
| 核心实现 | ~260 行（aggregators + specs + 错误类）+ 测试/demo/specs |

同时：

1. `execution-derived-outputs` 仍以 MUST 要求这些原语（r755/r160/r199），使「未进 YAML 主线」的能力继续绑定契约与测试面。
2. cardinality 护栏移除时保留了 IR `DedupBySpec.on_conflict`，并在 yaml-dsl specs 中写了「YAML `dedup_by.on_conflict` 继续保留」——但 YAML 根本没有该字段，**契约已漂移**。
3. 这不是护栏，但是**零外部用量的重能力**；业务替代路径清晰（loader 去重；workflow 两段 demand）。

权衡：失去单进程内 dedup-then-agg / two-stage 一等 IR；换取更薄的 derived-outputs 表面，并修正漂移契约。`count_distinct` / 普通 `group_by` / rank / post `compute|call_by` **保留**。

与 `c0-remove-book-budget-policy` **无硬依赖**，可并行或同版打包。

## What Changes

**移除**

- IR / 公开导出：`DedupBySpec`、`DerivedDedupByGroupBySpec`、`TwoStageGroupBySpec`（`execution/output_composition`）
- 运行期：`DedupByThenAggregator`、`TwoStageGroupByAggregator`、`ScalimDedupKeyConflictError`
- 策略枚举：若仅服务 dedup → 删除 `DedupOnConflictPolicy`；确认无其它引用后再删
- 测试：`tests/yaml_dsl/test_derived_outputs.py` / `tests/execution/test_output_composition.py` 中相关用例
- Demo：`notebooks/.../ch120_derived_set_aggregations.py`、`packages/scalim-misc/.../derived_set_aggregations_demo.py`（删除或改写为「用两段 demand / loader 去重」示例）
- Specs：`execution-derived-outputs` 删除/改写 r755、r160、r199；清理 key-normalization 中仅服务 dedup 的场景表述（若仍覆盖 group_by 则保留 group_by 部分）
- yaml-dsl specs：删除/改写误写的 YAML `dedup_by` / `dedup_by.on_overflow` / `on_conflict` 场景（与「YAML 从未暴露」对齐）；capability-matrix「dedup_by / 两阶段走 Python-only」改为「已移除」
- 升级文档：新增 `YYYY-MM-DD-remove-dedup-and-two-stage-derived.md`；修订 `2026-03-13-derived-outputs-set-aggregations.md` 历史描述中「现行能力」口吻

**迁移（无兼容层）**

| Before | After |
|---|---|
| `DerivedDedupByGroupBySpec(dedup_by=DedupBySpec(...), group_by=...)` | loader / 上游先去重，或接受重复行后只用 `DerivedGroupBySpec` |
| `TwoStageGroupBySpec(stage1=..., stage2=...)` | workflow 两个 demand/run：stage1 写出中间表 → stage2 再聚合 |
| 捕获 `ScalimDedupKeyConflictError` | 类型删除 |

**明确不改**

- `DerivedGroupBySpec` + metrics（含 `count_distinct`、`count_true`、`count_true_gte`）
- rank / post `compute`/`call_by`
- BookBudget / write policy（见 `c0-remove-book-budget-policy`）

## Capabilities

- `execution-derived-outputs`（主）
- `ir-key-normalization`（dedup_by 相关场景收窄）
- `yaml-dsl-write-policy-and-output-extras`（清理误写 YAML dedup 条款，若仍挂在此 capability）

## Impact

- **BREAKING**：Python IR 删除三类 Spec 与相关错误类型；指纹 kind `dedup_by` / `dedup_by+group_by` / `two_stage_group_by` 不再出现。
- YAML 作者面：无直接破坏（本未暴露）；仅文档/错误文案清理。
- 并行模式：`on_conflict=first|last` 与 `adaptive` 互斥约束随能力删除。

## Follow-ups（工具链更新后再补）

- [ ] `design.md`：替代路径示例（loader vs 两段 workflow）+ cardinality 文案漂移清理表
- [ ] `tasks.md` + delta specs
- [ ] `llman sdd validate c10-remove-dedup-and-two-stage-derived --strict`
- [ ] 确认 `DedupOnConflictPolicy` 无残余引用后再删
