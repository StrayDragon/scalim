## ADDED Requirements

### Requirement: workflow emits workflow-level events and injects attribution for demand events
workflow 执行 MUST 提供可观测性桥接层,用于将 per-demand 事件流稳定归因到 workflow YAML 的节点 id,并提供最小的 workflow-level 事件集合.

workflow MUST 生成一个 `workflow_exec_id` 并贯穿一次 workflow 调用的生命周期.

对每个 demand 节点,workflow MUST:
- 将 `workflow_exec_id` 与 `workflow_node_id` 注入到该 demand 事件流的 `Event.meta` 中
- 保持 demand 事件流的 `Event.run_id` 语义不变(仍为一次 demand 执行标识)

workflow 同时 MUST 发出最小集合的 workflow-level 事件:
- `workflow_node_start`
- `workflow_node_end`
- `workflow_node_cancelled`

对 workflow-level 事件:
- `Event.run_id` MUST 等于 `workflow_exec_id`(形成 workflow 事件流的稳定分区)
- `Event.seq` MUST 在该 `run_id` 内单调递增
- `Event.meta` MUST 同时包含 `workflow_exec_id` 与 `workflow_node_id`

#### Scenario: demand events can be joined back to workflow node ids
- **GIVEN** workflow YAML 声明 runs: A/B
- **WHEN** workflow 并发执行 A/B 两个 demand
- **THEN** A 的 demand 事件 `Event.meta.workflow_node_id` MUST 等于 `"A"`
- **AND** B 的 demand 事件 `Event.meta.workflow_node_id` MUST 等于 `"B"`
- **AND** A/B 的 `Event.meta.workflow_exec_id` MUST 相同(同一次 workflow 执行)

#### Scenario: workflow-level events have workflow_exec_id run partition
- **WHEN** workflow 调度开始/结束/取消某个节点
- **THEN** 对应的 workflow-level 事件 `Event.run_id` MUST 等于 `workflow_exec_id`
- **AND** `Event.meta` MUST 包含 `workflow_exec_id` 与 `workflow_node_id`

### Requirement: max_concurrency>1 requires thread-safe or stateless components
当 workflow 的 `max_concurrency>1` 时,系统 MUST 明确同一 `components` 列表中的 hook/observer 实例可能被多个并发节点复用的运行时契约:
- `max_concurrency>1` 时,components MUST 为线程安全或无状态
- 否则行为未定义且不保证正确性;调用方 SHOULD 将 `max_concurrency` 降为 1

#### Scenario: documentation makes component concurrency contract explicit
- **WHEN** 用户开启 `max_concurrency>1`
- **THEN** 系统规范 MUST 明确 components 的线程安全/无状态要求
