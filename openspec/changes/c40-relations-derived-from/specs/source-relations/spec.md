## ADDED Requirements

### Requirement: relation `from` MAY reference pre-relation derived fields on main_source side
系统 SHALL 允许 relation steps 的 `from` 引用顶层 derived field 作为 join key，但必须满足严格边界：
- 仅允许出现在 `from`（main_source 侧），`to` MUST NOT 引用 derived fields
- 引用语法仍为 `source.field`：当 `source==main_source.source_id` 且 `field` 命中顶层 derived field 时视为合法
- 仅允许引用 “pre-relation 可计算” 的 derived field：其依赖闭包 MUST NOT 包含任何需要 `LoadRef` 才能得到的字段（ref 字段/带 relation 的字段）
- 当违反以上约束时，系统 MUST 在编译/校验阶段 fail-fast 并输出可诊断错误（包含阻塞依赖链摘要）
- 当 relation `from` 依赖 derived field 时，系统 MUST 在该 relation 对应的 LoadRef 发生前完成该 derived field 的计算

#### Scenario: broadcast constant derived key can be used as relation `from`
- **GIVEN** 顶层 derived field `_broadcast_key` 定义为常量（例如 `compute: "1"`）
- **AND** 某个 relation step 的 `from` 使用 `<main_source_id>._broadcast_key`
- **WHEN** demand 被编译并执行
- **THEN** relation 校验 MUST 通过
- **AND** LoadRef 的 lookup key MUST 可读到 `_broadcast_key` 的计算值

#### Scenario: derived key that depends on ref fields is rejected
- **GIVEN** 某 derived field `k` 的 dependencies 中包含一个 ref 字段（必须经 LoadRef 才能得到）
- **WHEN** relation step 的 `from` 引用 `<main_source_id>.k`
- **THEN** 配置校验 MUST 失败并指出 `k` 不是 pre-relation 可计算
