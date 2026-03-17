## ADDED Requirements

### Requirement: workflow attribution meta is injected incrementally and wants-gated
系统 MUST 支持在 `Event.meta` 中注入 workflow 归因字段:
- `workflow_exec_id`: 标识一次 workflow 执行(一次调用内稳定)
- `workflow_node_id`: 标识事件来自哪个 workflow 节点(对 demand 节点等于 workflow YAML 的 `runs[*].id`)

归因注入 MUST 通过“增量合并 meta”实现:
- MUST NOT 改写既有 `Event.run_id` 语义(仍表示一次 demand 执行)
- MUST NOT 改写既有 `Event.seq` 语义(仍由发送端在 `run_id` 内单调递增)

归因注入 MUST wants-gated:
- 当事件不会被发送到 observers 或 `hook.on_event(Event)` 路径时,MUST 不构建 `Event` envelope,也 MUST 不做 meta 注入/复制.

#### Scenario: demand events carry workflow attribution without changing run_id/seq
- **GIVEN** workflow runner 为某次 demand 执行配置了 workflow attribution 注入
- **WHEN** demand 执行过程中发出任意 catalog 事件
- **THEN** 发给 observers/`hook.on_event` 的 `Event.meta` MUST 包含 `workflow_exec_id` 与 `workflow_node_id`
- **AND** `Event.run_id` MUST 保持 demand run_id 语义不变
- **AND** `Event.seq` MUST 继续按既有语义递增

### Requirement: workflow attribution meta keys are reserved and override must fail fast
`workflow_exec_id` 与 `workflow_node_id` MUST 视为保留 key.
当系统已注入这些字段时,若用户/下游组件试图在同一次事件分发中覆盖同名 key,系统 MUST fail-fast 抛出错误,避免归因被悄悄篡改导致观测数据不可解释.

#### Scenario: overriding workflow attribution keys fails fast
- **GIVEN** 系统已为某次 demand 执行启用 attribution 注入
- **WHEN** 调用方尝试在 `Event.meta` 中显式传入 `workflow_exec_id` 或 `workflow_node_id`
- **THEN** 系统 MUST 立即抛出错误并指出该 key 为保留字段

### Requirement: workflow event namespace is reserved for future extensions
系统 MUST 将 workflow-level 事件与未来扩展事件纳入统一事件目录,并保留以下稳定命名空间前缀:
- `workflow_node_*`
- `workflow_cache_*`
- `workflow_resource_*`

后续变更在新增 workflow/cache/resource 事件时 MUST 复用上述前缀与归因字段,以保证可稳定 join 回 workflow DAG 视图.

#### Scenario: future workflow events reuse reserved prefixes and attribution
- **WHEN** 后续变更新增一个 workflow/cache/resource 生命周期事件
- **THEN** 该事件类型名称 MUST 以 `workflow_node_`/`workflow_cache_`/`workflow_resource_` 之一作为前缀
- **AND** 该事件 MUST 复用 `workflow_exec_id` 与 `workflow_node_id` 归因字段
