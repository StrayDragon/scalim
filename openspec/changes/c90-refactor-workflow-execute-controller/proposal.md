## Meta

- Type: `refactor-0`
- Topic: workflow 执行层“巨石化”拆分为显式 Controller/State（降低回归风险、提升可测试性）
- Related code (热点与症状):
  - `src/scalim/workflow/execute.py:1107`（`_workflow_process_completed_future`，C901）
  - `src/scalim/workflow/execute.py:1210`（`_execute_workflow_run`，C901）
  - `src/scalim/workflow/execute.py:1658`（`_replay_captured_workflow_observability`，C901）
  - 资源提交与失败策略交织：`src/scalim/workflow/execute.py:1560`~`:1573`（commit/discard）

## 背景

workflow 执行层承担了多个不同维度的职责：

- 调度：ready queue、max_concurrency、future 提交/回收、取消策略；
- 正确性：failure_policy（`all_fail` 等）、节点状态机、outcome 汇总；
- 资源：in-memory artifacts 生命周期、资源 manager commit/discard；
- 性能：cache_pool、preload/cache reuse；
- 可观测性：emit node start/end、capture/replay hook/observer events；
- viz：workflow snapshot 写入、子运行 replay 链接修复。

这些职责目前主要聚集在少数长函数/闭包中，通过多个 dict/holder 共享状态完成协作。结果是：

- 复杂度高（多处 `# noqa: C901`）；
- 改动成本高、回归风险大；
- 单测难：很难针对某个子职责做局部测试，只能做大集成；
- 诊断困难：失败路径遗漏 cleanup/emit 很难被 review 捕捉。

该 refactor-0 的目标是：**把工作流执行逻辑改造成显式的“状态机/控制器”**，并在不改变对外行为的前提下，逐步拆分职责边界。

## 例子（为什么需要 Controller）

以 `_workflow_process_completed_future` 为例，它既要：

- 处理 future 的三种结局（成功/异常/取消）；
- 把异常映射为 `WorkflowRunOutcome` + diff；
- 更新 node_state/outcomes；
- 触发 artifact/cache_pool 的释放；
- 根据 failure_policy 做取消未启动节点；
- 收集并回放 observability/viz 数据；
- emit node end 事件。

这已经不是“一个函数”能稳定承载的复杂度，而更像是一个 `WorkflowRunState` 的 `on_future_done(...)` 事件处理。

## 目标

- 不改变行为：对外 API、workflow 语义、事件口径、资源输出保持一致；
- 拆分成可命名组件：
  - Scheduler（提交/回收/取消）
  - OutcomeBuilder（异常到结果映射）
  - ResourceLifecycle（artifacts/cache_pool/resource_manager）
  - ObservabilityCaptureReplay（capture/replay）
  - VizSnapshotWriter（snapshot 原子写、child replay 链接）
- 逐步迁移：每一步可独立 review/回滚；
- `src/scalim/` 保持 Python 3.6 兼容（使用 `src/scalim/vendor/dataclassesx`）。

## 推荐方案（分阶段）

### Phase 0：引入显式 State/Controller，但先不搬逻辑（最小改动）

做法：

- 新增 `src/scalim/workflow/execute_controller.py`，并在其中定义 `WorkflowRunState`（dataclass）承载当前散落的状态：
  - `outcomes`, `node_state`, `failed_outcome_holder`, `failed_exc_holder`
  - `ready_queue`, `submitted`, `max_concurrency`, `failure_policy`
  - `captured_*` 等 capture 容器
- 在同一模块中新增 `WorkflowRunController`：
  - 构造时注入依赖（executor、resource_manager、instrumentation、cache_pool 等）
  - 提供方法壳：`submit_ready_nodes()`, `process_completed_future()`, `finalize()`
- 先在 `execute.py` 里把现有函数逻辑搬到 controller 方法内（“剪切粘贴式迁移”），但保持同样的控制流与调用顺序。

收益：

- 立刻把隐式状态收拢为显式对象；
- 为后续拆分提供结构支点；
- 风险相对可控（行为变化最小）。

### Phase 1：抽离纯函数与规则模块（降低复杂度）

优先拆出的模块（收益最大）：

- `OutcomeBuilder`：异常/结果 → `WorkflowRunOutcome`（含 safe_error_message/type/diff）
- `EventClassifier`：对 capture 的 observer events 做分类/分桶（目前在 `_replay_captured_workflow_observability`）
- `SchedulerRules`：failure_policy 的终止条件/取消策略

### Phase 2：明确资源/缓存生命周期（减少漏清理风险）

将以下职责收敛为明确方法：

- `on_node_terminal(node_id, ok)`：负责 artifacts release、cache_pool.on_workflow_node_done、emit 等
- `finalize_commit_or_discard()`：统一 commit/discard，保证异常路径一致

## 方案对比

### 方案 A：只拆函数（不引入 Controller）

优点：

- 改动更小。

缺点：

- 状态仍隐式散落，复杂度只是从“一个函数”扩散为“多个函数”；
- 很难避免 side effects 漏掉。

### 方案 B：Controller/State（本提案推荐）

优点：

- 能把复杂度建模成状态机；
- 更适合 workflow 这种天然状态驱动的问题域；
- 单测可以围绕 controller 的状态转换来写。

缺点：

- 初期改造面更大，需要更严格对拍与测试。

## 性价比

- 成本：中到高（核心链路重构，必须谨慎）。
- 收益：高（长期维护成本显著下降；bug/回归更容易定位；新能力更容易加）。

## 风险与回滚

- 风险：行为不小心改变（尤其是取消/失败策略/事件顺序）。
- 缓解：
  - Phase 0 采用“结构重排但不改逻辑”的迁移策略；
  - 增加对拍测试：outcomes 列表、node_state、关键事件序列；
  - 对 viz snapshot/events 做结构化快照（允许非关键字段变化）。
- 回滚：
  - 每个 phase 独立提交；
  - Controller 引入阶段可通过开关回退到旧路径（仅在迁移期使用，最终移除）。

## 验证建议

- 必跑：`just quick-qa-only-py` + `just test`（或最小 workflow 覆盖子集）。
- 针对 workflow：
  - 失败策略矩阵（all_fail/primary_only 等）；
  - cache_pool 开启/关闭；
  - capture_observability 开启/关闭；
  - viz 启用/关闭；
  - 资源 commit/discard 路径覆盖。
