## Context

workflow 执行层当前承担调度、失败策略、资源生命周期、cache_pool、可观测性 capture/replay、viz snapshot 写入等多维职责，但主要聚集在少数长函数/闭包中，并通过多个 dict/holder 共享隐式状态（多处 `# noqa: C901`）。

这种结构的长期成本：

- 复杂度高、回归风险大：某条异常路径漏 cleanup/emit 很难在 review 中被捕捉
- 单测难：难以针对某个子职责做局部测试，只能依赖全链路集成
- 演进受阻：新增 failure_policy/诊断能力/资源策略会进一步加深嵌套与 side effects

workflow 运行本质上是一个状态机：ready/submitted/completed 的迁移、失败策略决策、资源 commit/discard、事件 emit 与 replay 都围绕“状态转换”发生。将其建模为显式 `Controller + State` 更符合问题域，也更利于测试与逐步重构。

约束：

- 不改变对外行为：API、语义、事件口径、资源输出保持一致
- 逐步迁移：每一步可独立 review/回滚
- `src/scalim/` 保持 Python 3.6 兼容（依赖 `dataclassesx`）

## Goals / Non-Goals

**Goals:**

- 将执行层改造成显式的 `WorkflowRunState` + `WorkflowRunController` 架构，收拢隐式状态
- 通过依赖注入明确边界（executor/resource_manager/instrumentation/cache_pool 等），降低隐藏耦合
- 为后续拆分子职责提供结构支点（OutcomeBuilder、SchedulerRules、ObservabilityReplay、ResourceLifecycle 等）
- 在保持行为一致的前提下逐步降低复杂度与 C901 风险

**Non-Goals:**

- Phase 0 不改变调度模型与 failure_policy 语义（先结构重排后语义治理）
- 不在本 change 中一次性完成所有模块化拆分（按 phase 逐步推进）

## Decisions

### 1) Phase 0：引入显式 State/Controller，并以“剪切粘贴式迁移”保持行为不变

Phase 0 的最小落地：

- 新增 `src/scalim/workflow/execute_controller.py`，并在其中定义 `WorkflowRunState`（dataclass）集中承载当前散落状态：
  - outcomes/node_state/failure holders
  - ready_queue/submitted/max_concurrency/failure_policy
  - capture/replay 容器（captured hook/observer/viz 等）
- 在同一模块中新增 `WorkflowRunController`：
  - 构造时注入依赖（executor、resource_manager、instrumentation、cache_pool、options 等）
  - 提供方法壳：`submit_ready_nodes()`、`process_completed_future()`、`finalize()`
- 在 `execute.py` 中把现有长函数逻辑搬进 controller 方法内部，保持控制流与调用顺序一致（先不做规则抽离）

该策略的目的：先把“隐式状态”变为“显式对象”，为后续拆分提供稳定锚点，同时将行为变化风险降到最低。

### 2) Phase 1：抽离纯函数与规则模块，降低复杂度并提升可测试性

优先拆出收益最大的纯逻辑模块：

- `OutcomeBuilder`：异常/结果 → `WorkflowRunOutcome`（错误类型/安全消息/diff）
- `EventClassifier`：对 capture 的 observer events 做分类/分桶（避免在 replay 函数内交织数据整形与 IO）
- `SchedulerRules`：failure_policy 的终止条件/取消策略（可用规则函数 + 单测矩阵覆盖）

这些模块应尽量纯（输入输出显式），并由单元测试覆盖分支矩阵。

### 3) Phase 2：明确资源/缓存生命周期的集中入口，减少漏清理风险

把易漏的 side effects 收敛到明确方法：

- `on_node_terminal(node_id, ok)`：统一 artifacts release、cache_pool.on_workflow_node_done、emit 等
- `finalize_commit_or_discard()`：统一 commit/discard，保证异常路径一致

并用对拍/集成测试覆盖 commit/discard 交错与 failure_policy 组合。

## Risks / Trade-offs

- **行为漂移风险**：核心链路重构最怕顺序/条件变化。缓解：Phase 0 严格“搬迁不改逻辑”，并增加对拍测试锁定关键序列（outcomes/node_state/关键事件）。
- **短期复杂度上升**：迁移期可能出现“旧函数 + controller 新壳”的双层结构；通过 phase 切片与及时删除旧路径控制。

## Migration Plan

- Phase 0：引入 State/Controller + 搬迁逻辑 + 增加对拍测试（行为不变）
- Phase 1：抽纯函数模块并加单测矩阵（降低复杂度）
- Phase 2：资源/缓存生命周期集中化（减少漏清理风险）

## Open Questions

- 无。
