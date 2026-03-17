## Why

当前 workflow 已有 YAML authoring surface 与 `run_workflow()` 实现,但它是“直接执行器”,并未与项目既有的 IR/执行结构对齐。随着需求扩展到 DAG、ctx 传递、共享输出容器、条件/选择器等节点类型,继续在 YAML 与 runner 上“叠字段/叠分支”会迅速失控(语义分散、难以验证确定性/并发/内存边界)。

我们需要先确立一个 **Workflow IR(节点系统)** 作为统一底座,让后续能力以“节点/工件/边”的形式演进,并将 YAML 语法后置为“编译到 IR 的前端”,避免反复推倒重来。

## What Changes

- **New**: Workflow IR v0（节点系统 + 工件传递）
  - 定义 workflow 内部统一数据结构: `nodes`/`deps`/`options`/`artifacts`
  - 以 demand 节点为起点,预留 condition/selector/output 等节点类型的扩展点
  - 明确确定性规则(并发下就绪节点 tie-break、结果对齐、取消语义)

- **SSOT**: workflow 的“两阶段编译”模型（用于统一后续 changes 的边界）
  - **结构编译（static / graph compile）**: workflow YAML → `WorkflowIr` 图（nodes/deps/resources/options + 静态校验 + 确定性顺序）
    - YAML 的 `runs[*]` 只是 authoring surface；编译后在 runtime 一律以 **workflow node** 为调度单元
    - `workflow_node_id` 来自 IR 的 node id；对 demand 节点等于 YAML 的 `runs[*].id`
  - **物化编译（dynamic / compile-on-ready）**: 当某个 node 满足 deps 且就绪时：
    - 渲染该 node 的输入（例如 `init_vars` / params template；可能依赖上游 ctx）
    - 编译 demand YAML → `DemandIr`（并执行）
  - 说明：ctx store 与 compile-on-ready 的细节由后续 `workflow-dag-context-passing` 变更落地；本 change 负责定义 IR 与调度底座,避免在 `run_workflow()` 直接执行器上持续打补丁

- **New**: Demand 节点间的“显式隔离 + 显式输入”
  - 一个 demand 只能看到其依赖的上游 demand 输出(不共享隐式全局状态)
  - 上游输出以 workflow-scope artifacts 形式存在,由 workflow runtime 统一管理生命周期

- **Implementation Deliverables (in this change)**
  - Workflow YAML -> Workflow IR 的结构编译器（静态校验 + deterministic order）
  - 基于 IR 的确定性调度器（ready 队列 + tie-break + 节点状态机）
  - 在不改变对外 API 的前提下，将 `run_workflow()` 内部迁移为“编译 YAML → IR → 执行”

## Follow-ups (out of scope for this change)

- 对现有 workflow YAML 的进一步演进路径
  - 现有 workflow YAML 将演进为“编译到 Workflow IR 的语法前端”
  - 语法本身并非本 change 的优先交付,但需要在后续 changes 中与 IR 对齐

- **Done**: yaml-init-vars（变量注入命名修正,已归档）
  - 已将 `{$runtime: <name>}`/`runtime_vars` 更名为 `{$init_var: <name>}`/`init_vars`
  - workflow 相关 changes 统一沿用该命名与边界(编译期解析 + 不透明 literal)

- **Active**: workflow-cache-pool（workflow-scope cache 设计升级）
  - 当前 `options.share_preload_cache: bool` 过于窄化
  - 将引入可配置的“缓存池/生命周期管理”(按需获取、引用归零自动释放),以更精细地控制内存与复用边界

- **Roadmap (follow-up changes, suggested)**:
  - `workflow-cache-pool`: workflow-scope 缓存池/生命周期/内存策略(替代单一 bool 开关)
  - `workflow-dag-context-passing`: DAG 编排 + scalar ctx 传递(依赖 IR 底座后落地)
  - `workflow-shared-output-containers`: 共享输出容器/写出节点(建议落到 output/resource 节点体系)
  - `workflow-artifact-datasets`: dataset/rows 级上游产物复用(内置 loader 方案 + key index 契约)

## Capabilities

### New Capabilities
- `workflow-ir`: 定义并实现 workflow 的 IR/节点系统/工件传递/确定性与取消语义(作为后续能力的底座)

### Modified Capabilities
- `yaml-dsl-workflow`: workflow YAML 从“直接执行器配置”演进为“编译到 Workflow IR 的语法前端”(后续 changes 推进)
- `yaml-runtime-vars`: 变量注入命名已统一为 `{$init_var: ...}` / `init_vars`(workflow 相关 change 统一沿用)
- `source-cache`: 将 workflow 级共享缓存从单一 bool 开关演进为可配置缓存池与生命周期(后续 changes 推进)

## Impact

- Code / runtime:
  - 新增 workflow IR 与节点调度/工件存储的运行时底座(与现有 IR 执行模型对齐)
  - 在不改变对外入口的前提下,将 `run_workflow()` 内部迁移到“编译 YAML → IR → 执行”的链路
- YAML authoring:
  - 短期不强推新语法；长期目标是让 workflow YAML 仅承载“节点图的声明”,并保持 demand YAML 仍以 loader/params 为核心表达
- Testing / determinism:
  - 需要新增覆盖: DAG 调度确定性、outcomes 对齐、failure_policy 语义、取消/失败传播边界
- Docs / governance:
  - 需要在后续 changes 中同步更新 `docs/doc/yaml-dsl/workflow.md`、升级指南与 canonical demo；并遵循生成物/注入块治理与 `just gen-docs`/`just qa`/`just openspec-check` 门禁
