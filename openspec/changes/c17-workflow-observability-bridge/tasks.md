## 1. Contracts & specs

- [ ] 1.1 定义保留归因字段：`workflow_exec_id` / `workflow_node_id`（写入 `Event.meta`）
- [ ] 1.2 定义 workflow-level 事件类型与命名空间：`workflow_node_start` / `workflow_node_end` / `workflow_node_cancelled`
- [ ] 1.3 定义 cancelled reason 的最小枚举与错误诊断文案（dependency_failed / upstream_cancelled / policy_all_fail）

## 2. Runtime wiring

- [ ] 2.1 在 workflow runner 生成 `workflow_exec_id` 并在节点执行上下文中传播
- [ ] 2.2 在 demand 事件分发处注入 attribution（wants-gated，保证 `Event.run_id`/`Event.seq` 语义不变）
- [ ] 2.3 在 workflow scheduler/编排层发出 workflow-level 事件（start/end/cancelled）

## 3. Extensibility hooks

- [ ] 3.1 提供事件目录/注册点（为 cache/resource 生命周期事件预留命名空间）
- [ ] 3.2 约束后续 changes：新增事件必须复用 attribution 字段并可 join 回 DAG 视图

## 4. Tests & gates

- [ ] 4.1 单测：`Event.meta` 注入正确、`run_id/seq` 不变
- [ ] 4.2 并发集成测：多 nodes 并发时 attribution 不串扰
- [ ] 4.3 运行 `just qa`
- [ ] 4.4 运行 `just openspec-check`
