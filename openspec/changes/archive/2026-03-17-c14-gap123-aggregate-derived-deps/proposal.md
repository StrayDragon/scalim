## Why

下游希望把“按比率排名 → 积分 → 综合分 → 综合二次排名”这类典型 KPI 链路尽量下沉到 YAML DSL，以减少 Python 侧大内存与自定义逻辑，同时复用 Scalim 的流式输出/缓存能力。

但 0.2.7 的 `outputs.*.aggregate` 目前存在三个关键缺口（见 `.tmp/downstream_report/gaps/01~03_*.md`）：

1) **无法按聚合后比率字段排名**：`rank.by` 只能引用 `group_by` 或聚合指标字段，不能引用派生字段（例如 ratio）。
2) **post 字段无法依赖 post**：`call_by` 不允许引用 `score_by_rank/call_by` 产生的字段，导致 `all_integral = s1 + s2` 这类综合分无法表达。
3) **不支持二次排名**：无法对 `all_integral` 再做一次 `rank`（rank-after-post / 多阶段 aggregate）。

这些限制本质上都是“派生字段依赖与执行顺序”问题：当前实现固定为 metrics → rank → post，且依赖范围被强约束，导致典型 KPI 报表无法完整落地。

## What Changes

- 统一升级 aggregate 的派生字段语义：把 rank/post 字段视为同一套“聚合后派生字段图（DAG）”，允许它们相互引用（在安全与确定性边界内），并以拓扑序执行。
- 支持 `rank.by/order_by` 引用聚合后派生字段（rank-by-ratio、rank-after-post），并提供清晰的循环依赖诊断。
- 放开 post 字段对 post 字段的依赖（例如 `all_integral = s1 + s2`），并保持执行确定性与 top_k 语义可预测。
- 引入更统一的语法：优先用安全表达式（`compute`）表达简单派生，避免过度依赖 `call_by` 的 hotfix 口子（仍保留 `call_by` 作为逃生阀）。

## Capabilities

### New Capabilities

- `yaml-dsl-aggregate-compute`: aggregate 场景的安全表达式派生字段（用于 ratio、求和、加权等简单派生）。

### Modified Capabilities

- `demand-dsl`: `outputs.*.aggregate.fields` 的依赖引用范围与执行语义升级（支持多阶段派生与二次排名）。
- `derived-outputs`: finalize 阶段的派生字段执行从固定顺序升级为依赖驱动的确定性执行（含 top_k 语义保持可预测）。
- `yaml-dsl-schema`: schema/hover MUST 解释派生字段引用规则、执行顺序与常见报错（循环依赖、缺失依赖等）。

## Impact

- YAML authoring：可直接表达“比率排名 → 积分 → 综合分 → 综合排名”的链路，迁移路径清晰，心智负担更低（依赖驱动而非手写阶段）。
- Runtime/code：主要改动集中在 aggregate 的编译校验与 finalize 执行计划；需要扩展 e2e 覆盖并确保 Python 3.6 兼容与结果确定性不回退。

