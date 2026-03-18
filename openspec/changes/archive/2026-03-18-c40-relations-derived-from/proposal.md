## Why

当前 relation step 的 `from`/`to` 仅允许引用“某个 source 内已声明的源字段”（`source.field` 且 `field` 必须在 `main_source.fields` / `sources.*.fields` 中出现）。顶层 `fields`（派生字段）不属于任何 source，因此无法作为 join key 被 relation 直接使用。

这会阻断一些非常常见且合理的建模方式：
- broadcast/join 场景想要一个常量 join key（例如 `_broadcast_key = 1`），但不得不在 SQL/loader 层塞一个常量列；
- join key 需要轻量归一化（trim/lower/拼接）时，无法在 YAML 层表达，只能回退到上游改造或 Python glue。

我们希望在不破坏 Scalim “省内存 + 可解释依赖”的前提下，谨慎增强：允许 **main_source 侧(from)** 使用一小类“可在 relation 之前计算完成”的 derived field 作为 join key。

## What Changes

- 允许 relation steps 的 `from` 引用顶层 `fields.*` 派生字段（仅作为 main_source 的“虚拟字段”）：
  - 仅允许出现在 `from`（main_source 侧），不允许出现在 `to`；
  - 引用语法保持 `source.field`：当 `source` 等于 `main_source.source_id` 且 `field` 命中顶层 derived field 时，视为合法。
- 新增强约束与 fail-fast：
  - 仅允许引用“pre-relation 可计算”的 derived field（其依赖闭包不得包含任何 ref 字段/relation 字段），否则配置校验失败并给出可诊断错误。
  - 保持 cycle detection：若 derived 与 relation 形成环依赖，必须在编译/校验阶段报错。
- 规划/执行链路增强：当 relation `from` 依赖 derived field 时，系统 MUST 在该 relation 的 LoadRef 发生前计算该 derived field（可能引入一个“pre-ref compute phase”）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `source-relations`: 扩展 relation `from` 的可引用字段集合（允许 main_source 侧引用受限 derived fields），并要求在 LoadRef 前完成计算。

## Impact

- 受影响代码（预期）：
  - validators：`src/scalim/dsl/by_yaml/config_parsing/validators/relations.py` / `.../validators/sources.py`
  - relation resolver/dep graph：`src/scalim/planning/builder_helpers/dep_graph.py`（确保 from_fields 的依赖信号包含 derived）
  - plan builder/operator order：`src/scalim/planning/builder_helpers/operators.py`（引入 pre-ref compute phase 或更通用的 topo 调度）
  - runtime：`src/scalim/execution/executor/...`（确保执行顺序满足新约束）
- 测试影响：
  - 新增 relation + derived join key 的集成测试（broadcast constant key 为最小用例）
  - 新增校验错误测试（不可 precompute 的 derived 被拒绝；环依赖报错可读）

