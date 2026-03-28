## MODIFIED Requirements

### Requirement: workflow events MUST be joinable to workflow snapshot nodes

`scalim-viz/workflow/viz_events.jsonl` MUST 承载 workflow 级事件流，并与 workflow snapshot 共享稳定的 node_ref 命名空间。

top-level workflow events MUST 至少覆盖：

- `workflow_started` / `workflow_finished`
- `workflow_node_started` / `workflow_node_completed`
- `workflow_node_cancelled`
- `workflow_cache_*`
- `workflow_resource_*`

这些事件的 `node_ref.id` MUST 能映射回 `scalim-viz/workflow/viz_snapshot.json` 中的某个节点。

#### Scenario: resource lifecycle events can highlight workflow graph nodes
- **GIVEN** workflow bundle 中存在 `books.kind=xlsx_memory` 的资源节点
- **WHEN** 事件流包含该资源的 `workflow_resource_write`
- **THEN** 该事件的 `node_ref.id` MUST 能映射到对应的 workflow resource node

