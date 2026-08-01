---
depends_on: []
---

## Why

宽表报表里，大量派生字段**只用于最终写出**，并不参与后续关联或其它派生依赖。当前执行仍会在 compute 阶段提前算完并写入 `BatchContext`，带来：

1. 多余的 `set_field_value` / 上下文驻留（内存与 CPU）；
2. 与「按字段扫全表」叠加时，放大「行数 × 字段数」固定开销。

合成 MVP（`.tmp/evidence/perf-baseline/`）显示：相对内存 sink，写出与宽派生都是端到端实际耗时（wall time）的重要组成部分；本 change **不**以替换 `openpyxl` 为主线，而是用 **延迟物化（late materialization / write-precompute）** 降低中间上下文成本。

约束（来自性能探索决议）：

- 用户脚本迁移成本高 → **零新 DSL**；旧需求定义不改字即可受益。
- **禁止**物化总开关、**禁止** YAML/字段级 `virtual`/`lazy` 新标记；late 仅靠 **现有** Plan/IR 字段依赖与消费者关系自动判定，不安全则保持早算。
- 内存：相对进程生命周期峰值 RSS，增幅须 **≤ 10%**；本优化预期常为持平或下降。
- 默认 `seq` 不得无故变慢。
- 第一期允许将 **无 `$ctx` 的 `call_by`** 纳入 late 集合（副作用**次数不变**，**时机可能后移到写出前**——须写入合约）。

## What Changes

- 在规划/运行时从 `ExecutionPlan` / IR **显式依赖**识别 `late_fields`（仅用于 `target_fields` 写出、不被后续 compute/LoadRef/key 消费）。
- Row sink（含 streaming）：在 `write_row` / `write_row_aligned` 之前按行计算 `late_fields`；结果写入待写出行，**默认不落** `BatchContext`。
- 同行内用 **row-local** 依赖缓存复用 `get_field_value`（不跨行、不跨批）。
- 第一期 late 候选：`compute_expr` 与 **无 `$ctx` / `ctx_attr` 的 `call_by`**；含 `$ctx` 的字段 **不得** late（保持现有 compute 阶段语义）。
- Column sink：第一期 **不做**（避免把 row 优化误做成 N 次列扫描）。
- 可观测性：仍发 `FIELD_COMPUTE`（避免订阅方丢事件）；通过稳定 `Event.meta`（如 `scalim_compute_phase=write_precompute`）区分阶段；不新增事件类型（除非 design 证明必须）。
- Specs：扩展/新增 execution 侧合约（建议挂 `execution-hotpath-fastpaths` 或新 capability `execution-write-precompute-derived-fields`，在 Specs landing 时二选一，避免双 SSOT）。
- 证据：`.tmp/repro/` + `.tmp/evidence/` A/B；`just bench-compare`；Python 3.6 smoke。

**不改**

- YAML DSL 字段写法；不引入 `call_groups`。
- Excel 依赖（`openpyxl`）与写出库替换。
- `parallel_mode` 语义（本优化与 seq/adaptive 正交）。

## Capabilities

### New Capabilities

- （无）默认行为变更并入既有域，不新建平行 capability。

### Modified Capabilities

- `execution-hotpath-fastpaths`：**SSOT**——增补晚算判定、写出前/写列前物化、`fast_fail`+discard、事件 phase、内存有界；并与「值语义保持」条款对齐表述。
- `output-sink-contracts` / row·column emission：交叉引用 discard 与写出钩入点（若条款需明示）。
- `ir-field-compute` / `execution-structure`：仅当判定规则需引用 IR 消费者关系时交叉引用。

## Impact

- **兼容**：旧脚本零改动；值语义保持；`call_by` late 时副作用时机后移须文档+spec 明示。
- **性能**：宽表「大量输出专用派生」预期端到端耗时下降（验收目标见 design：建议 ≥15% 于约定 MVP shape）。
- **内存**：预期峰值持平或下降；若上升须 ≤10%。
- **维护**：判定规则只从 Plan/IR 显式边推导；单测锁定「被下游消费则禁止 late」。
- **风险**：streaming 下写出前缀与 fast_fail 交互；第一期以测试矩阵钉死。

## Ethics

- `ethics.risk_level`: medium（改变计算发生阶段，影响副作用时机与观测 phase）
- `ethics.prohibited_actions`: 静默改变含 `$ctx` 的 call_by 语义；引入按总行数线性增长的跨批缓存；为过门禁在默认分支提交 live specs（本壳不 start）
- `ethics.required_evidence`: MVP `result.json`（时间 + 峰值 RSS）；值相等对拍；py3.6 smoke
- `ethics.refusal_contract`: 若无法在无新 DSL 下证明值相等与 ≤10% RSS，不得宣称默认开启
- `ethics.escalation_policy`: 若需对含副作用的 call_by 改变「调用次数」，必须另开显式语法 change，不得塞进本 change
