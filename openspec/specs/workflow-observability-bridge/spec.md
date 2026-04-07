# workflow-observability-bridge Specification

**状态: ✅ 已实现**

## Purpose
定义 workflow 运行上下文与既有 hooks/observers 事件流的桥接契约,使 demand 事件可稳定归因到 workflow 节点,并提供最小的 workflow-level 编排事件.

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/yaml_dsl/workflow_entrypoints.py` (workflow runner + workflow-level 事件)
- `src/IMPL_ROOT/execution/run_ir.py` (按需注入事件 meta)
- `src/IMPL_ROOT/ob/manager.py` (`ObserverManager` meta 合并)
- `src/IMPL_ROOT/ob/hub.py` (`InstrumentationHub`)
- `src/IMPL_ROOT/events/catalog.py` (workflow 事件目录与命名空间)
- `src/IMPL_ROOT/events/event.py` (`Event` envelope)
- `src/IMPL_ROOT/events/events.py` (workflow-level 事件 payload)

## Requirements

### Requirement: workflow attributes demand events for stable DAG correlation
系统 MUST 在 workflow 执行中为每个 demand 节点的事件流提供稳定的归因信息,以便 hooks/observers/scalim-viz 能将事件关联回 workflow DAG:
- 事件 envelope (`Event`) 的 `meta` MUST 支持携带 workflow 归因字段
- 对 demand 节点发出的事件,`Event.meta` MUST 至少包含:
  - `workflow_exec_id`: 标识一次 workflow 执行(同一次调用内稳定;跨调用可不同)
  - `workflow_node_id`: 标识该事件来自哪个 workflow 节点(对 demand 节点等于 workflow YAML 的 `runs[*].id`)
- 系统 MUST 保持 `Event.run_id` 的既有语义不变(仍表示一次 demand 执行的运行标识),不得用 workflow node_id 覆盖它

#### Scenario: demand events can be joined back to workflow runs
- **GIVEN** workflow 声明 run A 与 run B,且存在订阅事件的 observer/hook(on_event)
- **WHEN** workflow 执行 run A 并触发任意执行事件(如 loader_call)
- **THEN** 观测到的事件 `Event.meta.workflow_node_id` MUST 等于 `"A"`
- **AND** 同一次 workflow 执行中,所有事件的 `Event.meta.workflow_exec_id` MUST 相同

### Requirement: workflow provides workflow-level observability events
系统 MUST 提供 workflow-level 事件,用于表达 workflow 节点的编排级行为,避免仅依赖 demand 事件流造成“调度不可见”:
- 系统 MUST 至少覆盖以下事件类型:
  - `workflow_node_start`
  - `workflow_node_end`
  - `workflow_node_cancelled`
- `workflow_node_cancelled` 事件 payload MUST 包含稳定的 `reason` 枚举值:
  - `dependency_failed`
  - `upstream_cancelled`
  - `policy_all_fail`

#### Scenario: cancelled nodes are observable
- **GIVEN** run B 依赖 run A
- **AND** run A 失败导致 run B 无法执行
- **WHEN** workflow 完成
- **THEN** workflow-level 事件流 MUST 包含 run B 的 `workflow_node_cancelled` 事件
- **AND** 该事件 payload.reason MUST 等于 `dependency_failed`

### Requirement: workflow preserves demand hooks/observers semantics
系统 MUST 在引入 workflow 编排能力后继续保持 demand 执行的 hooks/observers 语义稳定:
- workflow MUST 仍复用既有的 demand 执行边界(等价于调用 `run_ir()`),不得绕开 `components` 装配与事件分发
- 每个 run MUST 具备独立的 `Event.run_id` 与单调递增的 `Event.seq`(仅在该 run 内保证局部有序;并发下允许跨 run 交错)

#### Scenario: per-run event streams remain isolated
- **GIVEN** workflow 并发执行 run A 与 run B 且二者均触发事件
- **WHEN** observer 收到事件流
- **THEN** run A 与 run B 的事件 `Event.run_id` MUST 可区分
- **AND** 在同一 `Event.run_id` 内 `Event.seq` MUST 单调递增

### Requirement: workflow event catalog is extensible for cache/resources
系统 MUST 为 workflow-level 事件提供可扩展的事件目录/命名空间,以允许后续变更在不破坏既有观测契约的前提下新增事件类型(例如 cache/resource 生命周期事件):
- 系统 MUST 为事件类型提供稳定前缀命名空间(例如 `workflow_*` / `workflow_cache_*` / `workflow_resource_*`)
- 系统 MUST 保证新增事件类型仍可复用相同的归因字段（`workflow_exec_id` / `workflow_node_id`）,并遵循同一套并发/确定性约束

#### Scenario: new workflow-level events remain joinable
- **GIVEN** 后续变更新增 workflow-level cache acquire/release 事件
- **WHEN** workflow 并发执行并触发这些事件
- **THEN** observer/hook MUST 能通过 `workflow_exec_id` / `workflow_node_id` 将这些事件 join 回同一个 workflow DAG 视图
