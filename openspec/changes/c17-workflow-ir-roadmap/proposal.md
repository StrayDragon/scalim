## Why

当前 workflow 已有 YAML authoring surface 与 `run_workflow()` 实现,但它是“直接执行器”,并未与项目既有的 IR/执行结构对齐。随着需求扩展到 DAG、ctx 传递、共享输出容器、条件/选择器等节点类型,继续在 YAML 与 runner 上“叠字段/叠分支”会迅速失控(语义分散、难以验证确定性/并发/内存边界)。

我们需要先确立一个 **Workflow IR(节点系统)** 作为统一底座,让后续能力以“节点/工件/边”的形式演进,并将 YAML 语法后置为“编译到 IR 的前端”,避免反复推倒重来。

## What Changes

> 本 change 以 roadmap 为目标,优先明确方向与拆分边界；实现排期与具体 YAML 语法在后续 changes 中推进。

- **New**: Workflow IR v0（节点系统 + 工件传递）
  - 定义 workflow 内部统一数据结构: `nodes`/`deps`/`options`/`artifacts`
  - 以 demand 节点为起点,预留 condition/selector/output 等节点类型的扩展点
  - 明确确定性规则(并发下就绪节点 tie-break、结果对齐、取消语义)

- **New**: Demand 节点间的“显式隔离 + 显式输入”
  - 一个 demand 只能看到其依赖的上游 demand 输出(不共享隐式全局状态)
  - 上游输出以 workflow-scope artifacts 形式存在,由 workflow runtime 统一管理生命周期

- **New**: dataset/rows 级上游输出复用的方向(不要求 demand YAML 引入新概念)
  - 方向: 复用现有 loader 概念,提供内置 loader 作为“从 workflow 上游获取”的入口(例如 `scalim.workflow.loaders:*`)
  - 下游 demand 通过正常 `main_source.loader`/`sources.<id>.loader` 引用该内置 loader,并通过 params 指定上游 run/artifact
  - **关键边界(先在 proposal 层收敛)**: 内置 loader 的“绑定发生在 demand 层”,workflow 只负责:
    - 提供 workflow-scope artifact store(生命周期/缓存/释放由 workflow runtime 统一管理)
    - 在 workflow 编译阶段做静态校验: demand 仅允许引用其依赖的上游 run 输出(防止绕开 DAG 约束直接读任意 run)
    - 不在 workflow YAML 层引入新的“sources 注入语法”(避免 demand/workflow 的职责纠缠)
  - dataset 以“可 lookup key 的索引”作为核心契约(面向 sources/ref join),并支持作为 main_source rows 流使用
  - dataset 允许为同一份上游 rows 派生多个 index(按需 lazy build + cache),以适配不同下游 `KeyIr`:
    - 例: 上游 run `extract_orders` 输出 rows(含 `order_id/user_id/...`)
      - 下游 run A 需要按 `order_id` lookup → `index(order_id) -> row`
      - 下游 run B 需要按 `user_id` lookup → `index(user_id) -> rows`
    - v0 先限定为“同一份 rows 派生多个 index”(不做跨 dataset 合并/物化新 dataset),避免爆炸式复杂度
  - MVP 先限制 `parallel_mode=seq`(避免跨进程/序列化复杂度);后续再评估 `adaptive`

- **Planned**: 对现有 workflow YAML 的重实现路径
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
- `workflow-ir`: 定义 workflow 的 IR/节点系统/工件传递/确定性与取消语义(作为后续能力的底座)
- `workflow-artifact-loaders`: 内置 loader 方案,使 demand 复用上游产物时不引入新的 demand DSL 概念(仍以 loader/params 表达)

### Modified Capabilities
- `yaml-dsl-workflow`: workflow YAML 从“直接执行器配置”演进为“编译到 Workflow IR 的语法前端”(后续 changes 推进)
- `yaml-runtime-vars`: 变量注入命名已统一为 `{$init_var: ...}` / `init_vars`(workflow 相关 change 统一沿用)
- `source-cache`: 将 workflow 级共享缓存从单一 bool 开关演进为可配置缓存池与生命周期(后续 changes 推进)

## Impact

- Code / runtime:
  - 新增 workflow IR 与节点调度/工件存储的运行时底座(与现有 IR 执行模型对齐)
  - `run_workflow()` 将在后续 changes 中逐步迁移到“编译 YAML → IR → 执行”的链路
- YAML authoring:
  - 短期不强推新语法；长期目标是让 workflow YAML 仅承载“节点图的声明”,并保持 demand YAML 仍以 loader/params 为核心表达
- Testing / determinism:
  - 需要新增覆盖: DAG 调度确定性、工件生命周期、取消/失败策略、dataset 索引一致性与内存护栏
- Docs / governance:
  - 需要在后续 changes 中同步更新 `docs/doc/yaml-dsl/workflow.md`、升级指南与 canonical demo；并遵循生成物/注入块治理与 `just gen-docs`/`just qa`/`just openspec-check` 门禁
