## Context

execution 层已经有清晰的“DSL-agnostic request/result”边界：

- `ExecutionRequest`：承载输出策略、components、guardrails、loader_retry、runtime_bindings 等运行期需求
- `ExecutionResult`：承载输出路径、统计、计划与可选 in-memory 工件
- `run_ir(demand_ir, request)`：统一执行编排入口

但目前 Tier1 curated public facade `scalim.execution` 仅导出 `ScalimEngine`，导致：

- 用户材料容易引用 `scalim.execution.run_ir` 等内部模块路径（导入路径漂移风险）。
- 用户更容易误用 “直接 new engine + 自己拼装 request” 的方式，承担过多编排细节。

本 change 的核心不是重写 execution 逻辑，而是 **重新组织 public surface**，把 “单一 options/request 对象驱动入口” 明确为官方主线。

约束：

- `src/scalim/**` 运行时需兼容 Python 3.6。
- public surface 变更不做兼容层；全仓调用点一次性升级。
- docs/skills/notebooks 只允许使用 curated entrypoints（遵循 `public-api-surface-governance`）。

## Goals / Non-Goals

**Goals:**

- 将 execution 的官方入口收敛为 options-only：
  - 推荐用法为 `scalim.execution.run_ir(demand_ir, request=ExecutionRequest(...))`
  - 允许提供一个更直观的 facade（例如 `scalim.execution.run(demand_ir, *, options=ExecutionRequest(...))`），但必须保持“单对象驱动”
- 调整 `scalim.execution.__all__`，将 `run_ir` 与 contracts 提升为 Tier1 public facade 的一部分（并被 public API catalog/jump-imports 覆盖）。
- 在不改语义的前提下强化 fail-fast：
  - `ExecutionRequest` 的非法组合尽可能在构造/校验阶段失败（或在 `run_ir` 的入口处集中校验），避免深层 late failure。
- 同步更新 docs/tests/notebooks 与 import-boundary gate，确保用户材料不再引用内部路径。

**Non-Goals:**

- 不重构 engine/pipeline 的内部模块组织（仅在必要时做极小调整以满足 exports/校验）。
- 不引入新的执行能力（例如新的并行调度策略）。
- 不把 execution contracts 迁移到 pydantic（保持 dataclasses）。

## Decisions

### Decision 1: `ExecutionRequest` 作为 execution 的唯一“options 对象”

理由：

- 与 YAML DSL 的“单一 options 对象驱动入口”原则一致。
- 现有 `ExecutionRequest` 已经覆盖主要 knobs；比新增一层薄 wrapper 更少重复。

备选方案：

- 新增 `ExecutionRunOptions` 并内部转换为 `ExecutionRequest` → 会引入两套并存契约与迁移成本，本 change 先不做。

### Decision 2: 在 `scalim.execution` 包级 facade re-export `run_ir` 与 contracts

实现策略：

- `src/scalim/execution/__init__.py` 直接 re-export：
  - `run_ir`
  - `ExecutionRequest` / `ExecutionResult`
  - `OutputSpec` / `ExportLayout` / `ObservabilitySpec`
  -（可选）`export_layout_from_demand_ir`
- `ScalimEngine`：
  - 保留为高级入口（是否继续位于 `scalim.execution.__all__` 由实现阶段决定）
  - 若保留，必须在 docs 中明确其为 advanced/low-level

这样用户材料可以统一写：

```python
from scalim.execution import ExecutionRequest, run_ir
```

而不是引用 `scalim.execution.run_ir` 模块路径。

### Decision 3: 校验策略以 “入口集中校验 + contracts 局部 __post_init__” 为主

- 对纯结构性约束（如类型/空值/范围）优先在 dataclass `__post_init__` 校验。
- 对跨字段组合约束（如 output_composition 与 sink 的互斥/覆盖规则）优先在 `run_ir` 入口集中校验，避免 contracts 过度复杂化。

## Risks / Trade-offs

- [风险] public exports 变更会影响导入路径 → [缓解] 不做兼容层，一次性升级全仓；用 public API suite + import-boundary gate 保证闭环。
- [风险] 扩大 `scalim.execution.__all__` 增加维护成本 → [缓解] 以 `public-api-manifest` 的 catalog + drift gate 约束，变更必须可审计。
- [风险] 校验前移可能改变错误类型/错误信息 → [缓解] 在 specs 中把 fail-fast 作为要求并补足测试覆盖，确保错误更可诊断而不是更“静默”。

## Migration Plan

1. 调整 `scalim.execution` facade exports，并更新 Tier1 curated entrypoints（必要时新增 marker）。
2. 更新 docs/skills/notebooks/tests 的导入路径，确保用户材料只使用 curated entrypoints。
3. 增补/更新 public API catalog 与 import smoke（`just gen-public-api-jump-imports` 可用于快速核对）。
4. 跑门禁：`just qa`、`just openspec-check`。

## Open Questions

- `ScalimEngine` 是否仍应作为 Tier1 facade 的默认导出？还是仅保留在子模块并从 curated surface 移除（更激进但更清晰）。
