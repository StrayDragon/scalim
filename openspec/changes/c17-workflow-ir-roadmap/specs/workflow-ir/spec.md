## ADDED Requirements

### Requirement: workflow compiles to a Workflow IR graph
系统 MUST 引入 Workflow IR 作为 workflow 的统一底座,并将 workflow 的 authoring surface(例如 YAML)视为“编译到 IR 的语法前端”,而不是直接驱动执行器分支逻辑。
Workflow IR MUST 至少包含:
- 节点集合(`nodes`),每个节点具备稳定 id 与 type
- 显式依赖/边(`deps`),以表达 DAG 与就绪条件
- workflow-scope 选项(`options`),用于并发/失败策略/资源与缓存策略等
- workflow-scope 工件/产物(`artifacts`),用于节点间显式传递与生命周期管理

#### Scenario: YAML frontend compiles into explicit nodes and deps
- **GIVEN** 一个 workflow 声明两个 demand runs,其中 B 依赖 A
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR MUST 包含 A/B 两个节点
- **AND** IR MUST 包含从 A 指向 B 的显式依赖边(或等价表示)

### Requirement: workflow scheduling is deterministic under concurrency
系统 MUST 在并发执行下仍保持确定性调度与结果对齐:
- 当多个节点同时就绪,调度器 MUST 以稳定规则选择下一个启动的节点(例如按声明顺序 tie-break)
- workflow 返回结果 MUST 与声明顺序稳定对齐(不得依赖并发完成顺序)

#### Scenario: ready-node tie-break does not depend on completion timing
- **GIVEN** 两个节点同时就绪且允许并发
- **WHEN** 多次运行同一 workflow
- **THEN** 节点启动选择与最终 outcomes 对齐规则 MUST 稳定(可对拍)

### Requirement: demand nodes only access upstream artifacts via explicit deps
系统 MUST 将 demand 节点之间的输入收敛为“显式 deps + 显式 artifacts”,并禁止隐式全局共享状态:
- 下游 demand 仅允许引用其依赖链上可见的上游 artifacts
- workflow 编译阶段 MUST 对“artifact 引用超出依赖范围”的情况 fail-fast

#### Scenario: referencing a non-dependency artifact is rejected
- **GIVEN** 下游 demand 尝试引用某个未声明为依赖的上游 run 产物
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告非法引用的 run_id/artifact
