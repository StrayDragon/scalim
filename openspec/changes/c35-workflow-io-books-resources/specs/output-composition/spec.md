## REMOVED Requirements

### Requirement: workflow-managed pathless CSV targets MUST support in-memory row sinks
**Reason**：pathless CSV (`container.type: csv` + `path: ""`) authoring surface 已被破坏性移除；workflow-managed 中间态不再通过输出目标的空路径表达。

**Migration**：使用 `resources.books` + `outputs_defaults.to.book`/`outputs[*].to` 表达输出契约；workflow runtime 内部可按需选择内存 artifact(例如 `InMemoryRows`)作为写入节点输入,但该 artifact 不再作为 YAML 可触发/可依赖契约的一部分。

