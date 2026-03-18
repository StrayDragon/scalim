## Context

现状约束：
- relation steps 的 `from/to` 被要求为 `source.field`，并且 `field` 必须在对应 source 的 `fields` 中声明；
- 顶层 `fields` 是 derived fields（`compute/call_by`），不属于任何 source；
- 因此 derived fields 不能作为 relation join key 使用。

更深层的执行约束来自当前的 plan builder：
- `build_plan_operators()` 会按固定顺序生成 operators：`LOAD` → `LOAD_REF` → `COMPUTE`；
- 这意味着 derived fields 的计算天然发生在所有 ref lookups 之后；
- 若允许 derived field 出现在 relation `from`，则必须在 `LOAD_REF` 之前产生该 derived 值，否则无法构造 lookup key。

因此，本提案的关键不是“放开 validator”，而是要同时定义：
1) 允许哪些 derived field 参与 relation（避免环与语义混乱）  
2) plan/operator 的顺序如何满足该依赖（且不牺牲 determinism 与内存目标）

## Goals / Non-Goals

**Goals:**
- 允许 relation steps 在 main_source 侧(from)引用 derived fields 作为 join key，覆盖 broadcast constant key 等典型场景。
- 增强必须是“可解释 + 可静态校验”的：不允许引入难诊断的运行期竞态/隐式阶段。
- 不破坏 Scalim 省内存目标：仍以流式 rows + 受控 compute 为主，不引入“把大表塞进 ctx/内存”的捷径。

**Non-Goals:**
- 不允许在 `to` 侧引用 derived fields（避免与“目标 source key”语义混淆）。
- 不试图让任意 derived expression 都能当 join key；只支持一小类 “pre-relation 可计算” 的 derived。
- 不在本提案中新增“main_source.fields 支持 compute/call_by”这样的更大表面（可作为替代方案/后续提案单独评估）。

## Decisions

### D1. 只允许 main_source 侧(from)引用 derived fields，且语法保持 `source.field`

决定：当 relation step 的 `from` 出现 `<main_source_id>.<field>`：
- 若 `<field>` 在 `main_source.fields` 中存在 → 按既有规则；
- 否则若 `<field>` 在顶层 `fields`（derived）中存在 → 允许，并将其视为 main_source 的“虚拟字段”；
- 其它 source 禁止引用 derived。

理由：不引入新语法，且与用户认知最接近（join key 来自主表）。

### D2. 引入 “pre-relation 可计算” 约束，并在校验阶段 fail-fast

决定：只有满足以下条件的 derived field 才允许出现在 relation `from`：
- 其依赖闭包不得包含任何需要 `LOAD_REF` 才能得到的字段（即 ref 字段/带 relation 的字段）；
- 依赖闭包必须无环（复用既有 cycle detection）。

实现思路（校验器/规划器共用一套判定）：
- 将字段分为两类：
  - **pre-ref available**：可在主加载后立刻获得（无 relation 的源字段）
  - **ref-only**：必须经 `LOAD_REF` 获得（含 relation/lookup_steps 的源字段）
- 计算 derived 的可前置集合 `pre_ref_derived`：若 derived 的 dependencies 全部在 `pre-ref available ∪ pre_ref_derived` 中，则可前置计算；否则不可。
- 当 relation `from` 引用 derived 时，必须属于 `pre_ref_derived`，否则报错并指出阻塞依赖链（例如依赖了 ref 字段）。

### D3. PlanBuilder 增加 pre-ref compute phase（最小侵入）

为了满足 D2 的执行顺序，决定对 operators 生成做最小改造：
- 仍保留 `LOAD` 在最前；
- 在 `LOAD_REF` 之前插入一段 `COMPUTE_PRE_REF`（实现上仍可复用 `COMPUTE` operator type，但生成顺序发生变化）：
  - 仅包含 `pre_ref_derived` 集合中的 derived fields，按 `field_order`（拓扑序）追加；
- 然后执行 `LOAD_REF`；
- 最后执行剩余 derived 的 `COMPUTE`（现有行为）。

替代方案（不选）：
- 完全改成按 operator deps 做 topo 调度：更通用，但实现与回归面更大，先不在 P2 引入。

## Risks / Trade-offs

- [规划器行为变化] compute 不再保证“全部在 LOAD_REF 之后”：缓解 → 仅前置一小类可证可计算的 derived，并用测试锁住行为。
- [概念复杂度上升] 用户需要理解“只有 pre-ref derived 才能当 join key”：缓解 → 错误信息必须输出阻塞依赖链，并在文档中明确边界与示例。
- [潜在内存影响] 更早计算 derived 可能影响释放策略：缓解 → 仅涉及少量 key 字段；且 derived 仍按行计算，不引入全量物化。

## Open Questions

- 是否需要引入更显式的 authoring surface（例如 `fields_pre_ref` 或 `main_source.virtual_fields`）来减少“虚拟字段”隐式规则？
- 对 broadcast 常量 key，是否更简单的做法是支持 `main_source.fields.*.default_value`？（可能作为更低风险替代方案）

