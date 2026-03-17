## ADDED Requirements

### Requirement: workflow nodes declare explicit DAG deps via `depends_on`
系统 MUST 扩展 workflow YAML,允许通过显式依赖声明表达节点之间的 DAG 关系:
- `workflow.runs[*].depends_on` MAY 存在且 MUST 为 run id 列表
- 系统 MUST 做静态校验:
  - 被引用的 run id MUST 存在
  - 图 MUST 无环(cycle detection)
  - 重复 deps MUST 被去重（保留首次出现的顺序）,不得影响确定性与可测试性

#### Scenario: dependent nodes start after prerequisites
- **GIVEN** workflow 中 node B 声明依赖 node A
- **WHEN** workflow 在并发模式下调度执行
- **THEN** 系统 MUST 在 node A 成功完成后才允许 node B 启动

#### Scenario: cycles are rejected before execution
- **GIVEN** workflow 中 A depends_on [B] 且 B depends_on [A]
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告可读的 cycle 路径（例如 `[A, B, A]`）

### Requirement: workflow provides a workflow-level ctx store (namespaced by `workflow_node_id`)
系统 MUST 在一次 workflow 执行中维护一个 workflow-level ctx store,用于在依赖边上传递小体量上下文:
- ctx MUST 以 `workflow_node_id` 为命名空间(对 demand 节点等于 workflow YAML 的 `runs[*].id`)
- ctx 值 MUST 为 JSON-like 小对象(标量/小 list/dict),并设置大小护栏
- 系统 MUST 禁止将 rows/dataset/大型输出放入 ctx；大对象必须通过 artifacts/resources 路径表达
- ctx store MUST 线程安全(并发执行下可安全读写)

#### Scenario: ctx is only readable from dependency closure
- **GIVEN** node C 未声明依赖 node A
- **WHEN** node C 尝试读取 `{$ctx: {node: A, key: output_path}}`
- **THEN** 系统 MUST fail-fast 并报告“ctx 引用超出 deps 可见范围”

### Requirement: ctx guardrails MUST be configurable via `workflow.options.ctx`
系统 MUST 提供 workflow-level ctx 护栏配置入口,并在超限时 fail-fast:

- `workflow.options.ctx` MAY 缺省（使用默认护栏）
- `workflow.options.ctx.max_value_bytes` MUST 为正整数（默认 65536）
- `workflow.options.ctx.max_bytes` MUST 为正整数（默认 1048576）

#### Scenario: ctx guardrails pass schema validation
- **WHEN** workflow YAML 包含 `workflow.options.ctx`
- **THEN** schema-only 校验 MUST 通过

### Requirement: demand nodes MUST publish a minimal default ctx summary
系统 MUST 为 demand 节点在完成时发布一组稳定的默认 ctx keys,用于减少 Python glue:
- `output_path`（字符串或 null；当无法推导/不适用时为 null）
- `total_rows`（整数或 null）
- `duration_secs`（浮点数；单位秒）

#### Scenario: downstream can consume default ctx keys
- **GIVEN** node B depends_on [A]
- **WHEN** node A 完成并发布默认 ctx summary
- **THEN** node B MUST 能通过 `{$ctx: {node: A, key: total_rows}}` 读取该值并注入其输入

### Requirement: `$ctx` directives are resolved during compile-on-ready materialization
系统 MUST 支持在 workflow YAML 的 `init_vars` 中引用上游 ctx,并在 node 就绪时渲染这些值:
- `{$ctx: {node: <upstream_node_id>, key: <ctx_key>}}` MUST 被视为指令节点(对象节点),而不是字符串插值
- `$ctx` 渲染 MUST 发生在 node 的“物化编译”阶段(compile-on-ready),以避免启动时 ctx 不可得的问题
- 渲染后的值 MUST 注入为 demand 编译期 `init_vars`,并复用既有 `{$init_var: ...}` 解析契约

#### Scenario: ctx-driven init_vars trigger compile-on-ready
- **GIVEN** node B depends_on [A]
- **AND** node B 声明 `init_vars: {x: {$ctx: {node: A, key: output_path}}}`
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 node A 完成并发布 ctx 后才物化编译 node B

### Requirement: failure propagation cancels downstream nodes deterministically
当 DAG 中上游失败/取消导致下游不可执行时,系统 MUST 以确定性方式取消这些下游 nodes:
- 若某 node 的任一 prerequisite 失败,该 node MUST NOT 执行
- 系统 MUST 将该 node 标记为 cancelled 并携带原因摘要(例如 dependency_failed)
- 在 `failure_policy=all_fail` 时,系统 MUST 取消所有未开始的 nodes,原因 MUST 为 `policy_all_fail`

#### Scenario: downstream nodes are cancelled on upstream failure
- **GIVEN** node B depends_on [A]
- **AND** node A 执行失败
- **WHEN** workflow 结束
- **THEN** node B MUST 以 cancelled 结束,且原因应指向上游依赖失败
