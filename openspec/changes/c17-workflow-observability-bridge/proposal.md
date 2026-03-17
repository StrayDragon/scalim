## Why

workflow 将按优先级逐步演进到 DAG 编排、cache pool、共享输出容器等能力。但现有 hooks/observers 体系以“单次 demand 执行(run)”为边界，workflow 层缺少一个稳定的“观测桥接层”，导致：
- demand 事件流无法稳定归因到 workflow YAML 的 `runs[*].id`（即 workflow node id；scalim-viz/排障 join 困难）
- 共享缓存/资源复用会改变事件可见性（例如 preload 复用时可能没有任何 loader_call 事件），让观察数据难以解释
- workflow 未来引入 condition/selector/output 等非-demand 节点后，这些节点的调度/取消/资源动作缺少可观测事件

因此需要一个前置变更，用“最小增量”的方式把 workflow 运行上下文与既有事件流/订阅机制连接起来，并把兼容契约收敛为可验证的规范。

## What Changes

- **New**: workflow 事件归因（attribution）能力
  - workflow 执行时为每个 workflow 节点提供稳定的归因字段：
    - `workflow_exec_id`: 标识一次 workflow 执行（同一次调用内稳定）
    - `workflow_node_id`: 标识该事件来自哪个 workflow 节点（对 demand 节点等于 workflow YAML 的 `runs[*].id`）
  - 归因信息以 **增量 `Event.meta` 字段** 的形式提供，不改写既有 `Event.run_id` 语义

- **New**: workflow-level 观测事件（不依赖 demand 事件）
  - 提供最小集合的 workflow-level 事件用于表达：节点调度/开始/结束/取消、依赖未满足导致的 cancelled、失败传播
  - 为后续 cache pool / 共享输出容器提供可观测钩子点：cache acquire/release/evict、resource lock/commit/discard（先定义语义与事件契约，具体事件集合可在后续收敛）

- **New**: hooks/observers 兼容契约（workflow 演进的硬约束）
  - workflow MUST 保持 “run = 一次 demand 执行” 的 hooks/observers 行为语义不变（仍复用 `run_ir()` 执行边界）
  - `components` MUST 仍是对外唯一装配入口（不引入新的 workflow 开关绕过装配）
  - 并发下组件复用的约束必须被明确：当 `max_concurrency>1` 时，components MUST 线程安全或无状态；否则行为未定义且不保证正确性（应将 `max_concurrency` 降为 1）

- **Non-Goals**
  - 不引入新的 demand DSL 概念（例如不在 demand 里新增 workflow 专用语法）
  - 不在本 change 内解决 rows/dataset 级 artifact 传递（该方向由后续 dataset/artifact 提案处理）

## Capabilities

### New Capabilities
- `workflow-observability-bridge`: 定义 workflow 执行归因字段（写入 `Event.meta`）与 workflow-level 事件契约，用于将 demand 事件流关联回 workflow DAG，并为 cache/resource 生命周期提供可观测入口

### Modified Capabilities
- `yaml-dsl-workflow`: workflow 执行在可观测性层面需要提供节点归因信息（`workflow_exec_id` / `workflow_node_id`），并明确 hooks/observers 在 workflow 并发下的组件复用约束
- `hooks-observability-structure`: 增补“事件归因字段注入/合并”的规范边界（保持 wants-gated 与热路径语义不变）

## Impact

- Runtime/code:
  - 影响 workflow runner 与观测分发边界（workflow 上下文注入、workflow-level 事件发出），并作为 `workflow-dag-context-passing` / `workflow-cache-pool` / `workflow-shared-output-containers` 的前置基础设施
  - 运行时必须保持 Python 3.6 兼容
- Spec/doc governance:
  - SSOT 为 `openspec/specs/**/spec.md` 与 changes 的 delta specs；不直接手改任何 `.gen.*` 或 injected blocks
  - 变更交付前需通过 `just openspec-check`（后续若涉及 schema/docs 生成，再按既有入口补齐 `just gen-docs`/相关生成脚本）
