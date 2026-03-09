## ADDED Requirements

### Requirement: ref loader binding can be expressed via params template directives
系统 SHALL 允许通过目标 source 的 `params` 模板内联指令(`$keys/$rows`)表达 ref loader 的入参与绑定模式,并用于 relation steps 的 `LoadRef` 调用.

#### Scenario: relation ref loader 通过 `$keys` 注入 lookup keys
- **GIVEN** relation steps 从 main_source 关联到 `sources.order_evaluations`
- **WHEN** `sources.order_evaluations.params` 使用 `$keys` 指令节点注入 lookup keys
- **THEN** 执行 `LoadRef` 时 MUST 将该步骤的 lookup keys 注入到模板对应位置并透传给 loader

### Requirement: `$rows` preserves rows barrier semantics for relations
系统 MUST 将 `$rows` 指令视为 rows 模式绑定,并保留 rows barrier 语义(例如 adaptive 下该层串行)以及 `cache_mode` 语义.

#### Scenario: `$rows` 触发 rows barrier
- **WHEN** 某个 relation 目标 source 的 params 模板中出现 `$rows`
- **THEN** 该 relation 对应的 `LoadRef` 执行 MUST 按 rows barrier 语义串行运行(不得作为可并行 keys 任务执行)

### Requirement: preload_forever sources reject `$keys/$rows` directives
系统 MUST 禁止在 `cache_mode: preload_forever` 的 source 的 preload 调用路径中使用 `$keys/$rows` 指令节点(因为 preload 不具备 ref 上下文).

#### Scenario: preload_forever params 模板包含 `$keys` 被拒绝
- **WHEN** `sources.customers.cache_mode=preload_forever`
- **AND** `sources.customers.params` 中出现 `$keys` 或 `$rows`
- **THEN** 编译或校验 MUST 失败并报告配置路径

