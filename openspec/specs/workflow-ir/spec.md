# workflow-ir Specification

## Purpose
定义 Workflow IR 作为 workflow 的统一底座,并将 workflow 的 authoring surface(例如 YAML)视为"编译到 IR 的语法前端",而不是直接驱动执行器分支逻辑.

## Related Concepts
- Workflow IR 图
- 两阶段编译模型
- 节点集合与依赖
- Workflow 选项
- 工件/产物
- 调度器
- 编译/调度实现

## Requirements

### Requirement: workflow compiles to a Workflow IR graph
系统 MUST 引入 Workflow IR 作为 workflow 的统一底座,并将 workflow 的 authoring surface(例如 YAML)视为"编译到 IR 的语法前端",而不是直接驱动执行器分支逻辑.
Workflow IR MUST 至少包含:
- 节点集合(`nodes`),每个节点具备稳定 id 与 type
- 显式依赖(`deps`),以表达 DAG 与就绪条件（IR MUST 以 `node_id -> [prereq_node_id, ...]` 的形式保留 deps 列表）
- workflow-scope 选项(`options`),用于并发/失败策略/资源与缓存策略等
- workflow-scope 工件/产物(`artifacts`),用于节点间显式传递与生命周期管理

#### Scenario: YAML frontend compiles into explicit nodes and deps
- **GIVEN** 一个 workflow 声明两个 demand runs,其中 B 依赖 A
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR MUST 包含 A/B 两个节点
- **AND** IR 中 node B 的 deps MUST 包含 `"A"`（等价于存在 A -> B 的依赖边）

### Requirement: Workflow IR defines stable node ids and a two-stage compilation boundary
系统 MUST 将 workflow 的执行边界收敛为"两阶段编译"模型,并为后续 DAG/ctx/资源等能力提供稳定的依赖与命名空间契约:
- **结构编译**: workflow YAML -> Workflow IR 图(节点/边/资源/选项 + 静态校验 + 确定性顺序)
- **物化编译**: 当某个节点 deps 满足且就绪时,系统再物化编译该节点的执行单元(例如编译 demand YAML -> Demand IR 并执行)
- Workflow IR 的 `node_id` MUST 稳定且全局唯一;对 demand 节点,`node_id` MUST 等于 workflow YAML 的 `runs[*].id`

#### Scenario: ctx-dependent nodes compile only when ready
- **GIVEN** workflow node B 依赖 node A
- **AND** node B 的输入需要读取 node A 发布的 ctx(例如用于渲染 `init_vars`)
- **WHEN** workflow 执行
- **THEN** 系统 MUST 在 node A 完成并发布 ctx 后才物化编译 node B(compile-on-ready),并确保结果确定性不依赖并发完成时序

### Requirement: workflow scheduling is deterministic under concurrency
系统 MUST 在并发执行下仍保持确定性调度与结果对齐:
- 当多个节点同时就绪,调度器 MUST 以稳定规则选择下一个启动的节点(例如按声明顺序 tie-break)
- workflow 返回结果 MUST 与声明顺序稳定对齐(不得依赖并发完成顺序)

#### Scenario: ready-node tie-break does not depend on completion timing
- **GIVEN** 两个节点同时就绪且允许并发
- **WHEN** 多次运行同一 workflow
- **THEN** 节点启动选择与最终 outcomes 对齐规则 MUST 稳定(可对拍)

### Requirement: demand nodes only access upstream artifacts via explicit deps
系统 MUST 将 demand 节点之间的输入收敛为"显式 deps + 显式 artifacts",并禁止隐式全局共享状态:
- 下游 demand 仅允许引用其依赖链上可见的上游 artifacts
- workflow 编译阶段 MUST 对"artifact 引用超出依赖范围"的情况 fail-fast

#### Scenario: referencing a non-dependency artifact is rejected
- **GIVEN** 下游 demand 尝试引用某个未声明为依赖的上游 run 产物
- **WHEN** workflow 被编译/校验
- **THEN** 系统 MUST fail-fast 并报告非法引用的 run_id/artifact

### Requirement: Workflow IR runtime MUST remain Python 3.6 compatible
系统 MUST 保持 Workflow IR 的核心运行时与编译/调度实现兼容 Python 3.6(与项目运行时边界一致),不得引入仅在较新 Python 版本可用的语言特性或标准库 API.

#### Scenario: Workflow IR modules import under Python 3.6
- **GIVEN** 运行时为 Python 3.6
- **WHEN** 导入 workflow IR 的核心模块(编译/调度/数据结构)
- **THEN** 系统 MUST 不因版本不兼容的语法/stdlib API 导致 `SyntaxError`/`ImportError`

### Requirement: WorkflowOptionsIr MUST carry resources_wait from YAML to runtime
系统 MUST 扩展 workflow 编译产物中的 options(IR),确保 runtime 能消费 workflow-level 的资源等待与诊断策略.

`resources_wait` 的配置来源 MUST 位于 runtime policy boundary（而不是 workflow YAML authoring surface）：

- Workflow IR 的 `options` MUST 包含结构化字段 `resources_wait`
- `resources_wait` MUST 至少包含:
  - `max_wait_s`
  - `diagnostics.enabled`
  - `diagnostics.warn_after_s`
  - `diagnostics.repeat_every_s`(可选)
  - `diagnostics.capture_owner_callsite`(可选)
- runtime 构造共享资源管理器时 MUST 仅依赖 IR options(不得再从资源定义隐式推断策略)

#### Scenario: options are present in compiled IR
- **GIVEN** 调用方通过 runtime entrypoints 提供 `workflow_runtime_options.resources_wait`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR 的 `options` MUST 包含对应字段且值与该 runtime policy 等价

### Requirement: WorkflowOptionsIr MUST carry output_staging from YAML to runtime
系统 MUST 扩展 workflow 编译产物中的 options(IR),确保 runtime 能消费 workflow-level 的 staging/publish 策略.

#### Scenario: output_staging options are present in compiled IR
- **GIVEN** workflow YAML 配置了 `workflow.options.output_staging`
- **WHEN** workflow 被编译为 Workflow IR
- **THEN** IR 的 `options` MUST 包含对应 `output_staging` 字段且值与 YAML 配置等价
