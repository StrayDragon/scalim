## Context

当前 workflow YAML 仅提供“批量并发执行多个 demand”的编排入口：`run_workflow()` 以每个 demand 执行为边界复用 `run_ir()`，hooks/observers 也以单次 demand 的事件流为边界工作。

随着 workflow 演进到 DAG 编排、ctx 传递、cache pool、共享输出资源与写出节点等能力，现有观测体系出现结构性缺口：

- 事件无法稳定 join 回 workflow DAG：`Event.run_id` 仍是 demand 运行标识，不等于 workflow 节点 id
- 缓存/资源复用会改变事件可见性（例如 preload 复用时可能没有任何 loader_call 事件），导致观察数据难以解释
- 未来引入非-demand 节点后，这些节点的调度/取消/资源动作缺少观测事件语义

约束：

- MUST 不改变 `Event.run_id` 与 per-run `Event.seq` 的既有语义
- MUST 复用既有 components 装配（Observer/Hook 仍是唯一对外入口）
- 运行时需兼容 Python 3.6；热路径应尽量 wants-gated，避免无谓开销

## Goals / Non-Goals

**Goals:**

- 定义并实现 workflow attribution：在 `Event.meta` 注入 `workflow_exec_id` / `workflow_node_id`
- 定义最小的 workflow-level 事件集合：`workflow_node_start` / `workflow_node_end` / `workflow_node_cancelled`
- 建立可扩展的 workflow 事件目录（为 cache/resource 生命周期事件预留命名空间与字段约定）
- 明确并发下 components 复用契约（线程安全/无状态要求），保证观测正确性与可解释性

**Non-Goals:**

- 不在本 change 内引入新的 demand DSL 语法
- 不改变 `Event` 结构签名（仅使用 `Event.meta` 增量字段）
- 不在本 change 内实现 DAG/ctx/cache/resource 的具体业务逻辑（仅提供观测桥接契约）

## Decisions

### 1) Attribution 字段与命名空间

- `workflow_exec_id`: 一次 workflow 调用生成一个 id，并贯穿整个执行生命周期
- `workflow_node_id`: workflow node 的稳定 id
  - 对 demand 节点：等于 workflow YAML 的 `runs[*].id`
  - 对未来非-demand 节点：来自 Workflow IR 的 node id

这些字段写入 `Event.meta`，并视为保留 key：若用户/下游组件试图覆盖同名 key，系统 MUST fail-fast（避免归因被悄悄篡改导致观测数据不可解释）。

### 2) 注入策略：增量 meta merge + wants-gated

- 归因注入通过“增量合并 meta”实现，不改变既有事件内容
- 在 wants-gated 场景下：只有当存在订阅/组件需要这些字段时才执行注入/复制，避免无谓分配

### 3) Workflow-level 事件：调度可见、与 demand 事件解耦

workflow-level 事件用于表达“编排层”行为，不依赖 demand 事件是否发生，避免“调度不可见”：

- `workflow_node_start`: node 被调度开始执行
- `workflow_node_end`: node 成功结束
- `workflow_node_cancelled`: node 因依赖失败/上游取消/策略取消而未执行

事件 payload 至少包含：`workflow_exec_id` / `workflow_node_id` / node_type；对 cancelled 事件还需包含 reason（例如 dependency_failed / upstream_cancelled / policy_all_fail）。

### 4) 可扩展事件目录（为 cache/resource 预留）

- 事件类型命名空间建议采用稳定前缀：`workflow_cache_*`、`workflow_resource_*`
- 后续 changes 新增事件时必须复用相同 attribution 字段与并发/确定性约束，保证 join 能力稳定

### 5) 并发与 components 复用契约

- 当 `max_concurrency > 1` 时，components MUST 为线程安全或无状态；否则行为未定义且不保证正确性（应将 `max_concurrency` 降为 1）

### 6) workflow-level 事件的封装与 `run_id` 规则

- workflow-level 事件 MUST 复用既有 `Event` 结构与 hooks/observers 分发通道（不引入新的 channel）
- 对 workflow-level 事件：
  - `Event.run_id` MUST 等于 `workflow_exec_id`（形成“workflow 事件流”的稳定分区）
  - `Event.seq` MUST 在该 `run_id` 内单调递增
  - `Event.meta` MUST 同时包含 `workflow_exec_id` 与 `workflow_node_id`

## Risks / Trade-offs

- [meta 注入开销] → wants-gated + 仅对必要事件做最小复制
- [run_id vs node_id 心智负担] → 在文档与错误信息中明确：`Event.run_id` 是 demand 运行标识；workflow 归因使用 `workflow_node_id`
- [并发下组件非线程安全] → 明确契约 + 测试覆盖并发隔离

## Migration Plan

- 该变更为增量：旧 observer/hook 不读取 `Event.meta` 时行为不变
- 后续 changes（cache pool / shared resources）在新增事件时统一复用该归因契约与命名空间

## Docs / Generated Boundaries

- SSOT:
  - 规范：`openspec/specs/hooks-observability-structure/spec.md` 与 `openspec/specs/yaml-dsl-workflow/spec.md`（实现阶段通过 sync 将本 change 的 delta specs 合入）
  - 运行时实现：`src/scalim/**`（必须保持 Python 3.6 兼容）
- Generated（禁止手改）：
  - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
- Drift / gates：
  - `just qa`
  - `just openspec-check`
