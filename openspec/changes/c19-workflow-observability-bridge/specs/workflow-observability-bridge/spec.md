## ADDED Requirements

### Requirement: workflow attributes demand events for stable DAG correlation
系统 MUST 在 workflow 执行中为每个 demand run 的事件流提供稳定的归因信息,以便 hooks/observers/scalim-viz 能将事件关联回 workflow DAG:
- 事件 envelope (`Event`) 的 `meta` MUST 支持携带 workflow 归因字段
- 对 demand run 发出的事件,`Event.meta` MUST 至少包含:
  - `workflow_exec_id`: 标识一次 workflow 执行(同一次调用内稳定;跨调用可不同)
  - `workflow_run_id`: 标识该事件来自哪个 workflow run(等于 workflow YAML 的 `runs[*].id`)
- 系统 MUST 保持 `Event.run_id` 的既有语义不变(仍表示一次 demand 执行的运行标识),不得用 workflow run_id 覆盖它

#### Scenario: demand events can be joined back to workflow runs
- **GIVEN** workflow 声明 run A 与 run B,且存在订阅事件的 observer/hook(on_event)
- **WHEN** workflow 执行 run A 并触发任意执行事件(如 loader_call)
- **THEN** 观测到的事件 `Event.meta.workflow_run_id` MUST 等于 `"A"`
- **AND** 同一次 workflow 执行中,所有事件的 `Event.meta.workflow_exec_id` MUST 相同

### Requirement: workflow provides workflow-level observability events
系统 MUST 提供 workflow-level 事件,用于表达 workflow 节点的编排级行为,避免仅依赖 demand 事件流造成“调度不可见”:
- 系统 MUST 至少覆盖: node_start/node_end/node_cancelled(或等价事件)
- 当某节点因依赖失败/上游取消而无法执行时,系统 MUST 发出 cancelled 事件并携带原因摘要(便于排障与可视化)

#### Scenario: cancelled nodes are observable
- **GIVEN** run B 依赖 run A
- **AND** run A 失败导致 run B 无法执行
- **WHEN** workflow 完成
- **THEN** workflow-level 事件流 SHOULD 包含 run B 的 cancelled 事件
- **AND** 该 cancelled 事件 SHOULD 提供“因依赖未满足”或等价原因

### Requirement: workflow preserves demand hooks/observers semantics
系统 MUST 在引入 workflow 编排能力后继续保持 demand 执行的 hooks/observers 语义稳定:
- workflow MUST 仍复用既有的 demand 执行边界(等价于调用 `run_ir()`),不得绕开 `components` 装配与事件分发
- 每个 run MUST 具备独立的 `Event.run_id` 与单调递增的 `Event.seq`(仅在该 run 内保证局部有序;并发下允许跨 run 交错)

#### Scenario: per-run event streams remain isolated
- **GIVEN** workflow 并发执行 run A 与 run B 且二者均触发事件
- **WHEN** observer 收到事件流
- **THEN** run A 与 run B 的事件 `Event.run_id` MUST 可区分
- **AND** 在同一 `Event.run_id` 内 `Event.seq` MUST 单调递增
