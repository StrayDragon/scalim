## ADDED Requirements

### Requirement: workflow runs may declare dependencies to form a DAG
系统 MUST 支持在 workflow runs 中表达依赖关系,使 workflow 可以被解释为一个 DAG(有向无环图)而不仅是 runs 列表:
- 每个 run MAY 声明其依赖的上游 run ids(字段名不在本 delta 中强制;实现时以 schema 为准)
- 调度器 MUST 仅在依赖全部成功完成后才调度当前 run
- 系统 MUST 做静态校验: 依赖引用必须存在,且依赖图 MUST 无环(发现环则 fail-fast)
- 即使并发调度,workflow 返回的 outcomes 顺序 MUST 仍与声明顺序稳定对齐(便于调用方对拍与 UI 对齐)

#### Scenario: depends_on enforces ordering under concurrency
- **GIVEN** workflow 包含 run A 与 run B,且 run B 依赖 run A
- **WHEN** `max_concurrency > 1` 导致存在并发执行可能
- **THEN** 系统 MUST 不得在 run A 完成之前启动 run B

#### Scenario: cycle is rejected before execution
- **GIVEN** workflow 中存在依赖环(例如 A 依赖 B 且 B 依赖 A)
- **WHEN** workflow 被加载/校验
- **THEN** 系统 MUST fail-fast 并报告存在 cycle
- **AND** 系统 MUST 不执行任何 run

### Requirement: workflow provides run-scoped context and can inject it into downstream runtime_vars
系统 MUST 支持在同一次 workflow 执行中维护“run 级 ctx(上下文)”,用于将上游 run 的产物传递到下游 demand 的编译/执行输入中:
- ctx MUST 以 run_id 为命名空间(避免不同 run 之间 key 冲突)
- 系统 MUST 支持将选定的 ctx 值注入到下游 run 的 demand `runtime_vars` 中,以复用 demand 侧现有 `{$runtime: <name>}` 能力
- 初期实现 SHOULD 限定 ctx 值为 JSON-like(标量/小集合/映射),并对大体量数据提供 guardrails(作为后续扩展)

#### Scenario: downstream demand can use upstream exported ids via runtime_vars
- **GIVEN** run A 产出一组 ids 并将其写入 workflow ctx
- **AND** run B 依赖 run A
- **WHEN** workflow 执行 run B 且将 run A 的 ids 注入为 run B 的 `runtime_vars.user_ids`
- **THEN** run B 的 demand 配置中 `{$runtime: user_ids}` MUST 能解析到该 ids 集合

