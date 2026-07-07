## Why

在“字段很多但逻辑很薄”的报表 workload 中，性能瓶颈常常不是单次函数体执行，而是 **Python 调用次数 = 行数 × 字段数** 的固定开销。

`c2` 主线中的 batch call 能把“按行调用”变成“按批调用”，但它要求用户把函数改写为“列式输入/列式输出”，迁移成本与心智负担更高；并且 batch 形态也会触发 `$ctx` 语义、错误粒度与调试方式的额外讨论。

因此需要另一个不依赖列式 API 的杠杆：在保持 **row-mode** 用户函数形态不变（或仅小幅改变返回值形态）的前提下，减少调用次数：

- **multi-output**：一次调用返回多个字段值（dict/tuple），由框架分发写回多个派生字段。
- **fusion**：多个派生字段共享一次调用的结果（显式 group 或纯函数下的显式复用），避免重复计算/重复调用。

## What Changes

> 说明：本提案放在 `openspec/notplan-changes/`，仅用于沉淀候选方向，尚未进入 active change 工作流；不保证近期交付。

探索并引入“多字段共享一次调用”的可选 DSL / IR 能力（推荐显式、可治理的 group 语义，避免隐式改变副作用次数）：

- 新增一种显式“派生分组”定义（候选 DSL 名称：`call_groups` / `derive_groups`）：
  - group 声明一次 `call_by`（仍为 row-mode：每行调用一次）。
  - group 声明 outputs（`output_key -> field_id` 或 `field_id -> output_key`）。
  - group 产生的结果只在当前行范围内分发写回（不做跨行缓存），默认不增加内存峰值。
- group 函数返回值形态候选：
  - `dict[str, FieldValue]`：键为 output_key（或 field_id），值为该字段值。
  - `tuple[...]`：按 outputs 定义的稳定顺序映射（更快但更易错）。
- 与可观测性/错误语义的候选约束：
  - 即使只调用一次，仍按字段维度发出 FieldComputeEvent（可带上 group_id 以便诊断）。
  - group 调用失败时：可选择“整组字段均写 None + 逐字段 ErrorEvent”，或“仅缺失键的字段写 None”（需要在 spec 中明确）。

## Relationship to batch call_by

该方向与 `call_by_mode="batch"`（列式输入/输出）互补：

- **multi-output/fusion 保持 row-mode**：用户函数仍是“按行调用一次”，因此 `$ctx` 的语义与类型保持不变（`$ctx.row_id` 仍是单行标识、`$ctx.values` 仍是单行 values）。
- **对 ctx-heavy 场景更友好**：如果真实业务的 `call_by` 强依赖 `$ctx.row_id` / `$ctx.values`，优先尝试 multi-output/fusion 往往比把 `$ctx` 引入 batch call_by 更容易治理（避免 batch ctx 类型歧义与额外分配）。

## Capabilities

### New Capabilities
- `execution-derived-call-fusion`: 定义派生字段的 group/fusion 语义、返回值映射、错误处理与事件一致性。

### Modified Capabilities
- `planning-operators`: 可能需要支持“group compute operator”（一次执行写回多个 field），以避免在执行层做隐式去重/缓存。
- `yaml-dsl-schema`: 若 DSL 引入 `call_groups` 等新字段，需要 schema hover 文案与校验规则同步更新。

## Impact

- **收益上限**：对“同一行内多个字段共享中间结果/共享一次调用”的场景，调用次数可从 `F` 降为 `G`（`G` 为 group 数），且不要求列式 batch API。
- **风险/治理**：multi-output/fusion 会改变“用户函数被调用的次数/边界”，必须是显式 opt-in，并且需要明确副作用与错误语义的边界；否则容易制造隐蔽行为差异。
- **实现影响面（预估）**：
  - YAML DSL：新增 group authoring 结构与校验。
  - IR：新增 group IR（或扩展 DerivedFieldIr 以支持 group 引用）。
  - planning：从“每个 derived field 一个 ComputeOperator”扩展为“group ComputeOperator + field 写回”。
  - execution：compute executor 需要支持一次调用写回多个字段，并在 events 层保持字段级事件一致性。
