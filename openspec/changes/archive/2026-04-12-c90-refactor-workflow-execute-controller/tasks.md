## 1. Phase 0：引入显式 `State` / `Controller`（搬迁但不改逻辑）

- [ ] 1.1 新增 `src/scalim/workflow/execute_controller.py` 并在其中定义 `WorkflowRunState`（dataclass）集中承载执行状态（ready/submitted/outcomes/node_state/capture 等），并保持 Python 3.6 兼容（使用 `dataclassesx`）
- [ ] 1.2 在 `src/scalim/workflow/execute_controller.py` 中定义 `WorkflowRunController`：构造时显式注入 executor/resource_manager/instrumentation/cache_pool/options 等依赖；提供方法壳 `submit_ready_nodes()` / `process_completed_future()` / `finalize()`
- [ ] 1.3 将 `src/scalim/workflow/execute.py` 中 `_execute_workflow_run` / `_workflow_process_completed_future` / `_replay_captured_workflow_observability` 的逻辑剪切迁移到 controller 方法内，保持调用顺序与行为一致（先不做规则抽离）

## 2. Phase 0 回归对拍（锁定行为不变）

- [ ] 2.1 增加对拍/快照测试：outcomes 列表、node_state 终态、关键事件序列（node start/end、commit/discard），确保结构重排不改变语义
- [ ] 2.2 覆盖 failure_policy 矩阵（all_fail/primary_only 等）、cache_pool 开关、capture_observability/viz 开关、commit/discard 交错路径

## 3. Phase 1：抽离纯函数与规则模块（降低复杂度）

- [ ] 3.1 抽出 `OutcomeBuilder`：异常/结果 → `WorkflowRunOutcome`（含安全错误消息/type/diff），并补单测矩阵覆盖
- [ ] 3.2 抽出 `EventClassifier`：对 captured events 做分类/分桶/归并（纯数据整形），并补单测覆盖
- [ ] 3.3 抽出 `SchedulerRules`：failure_policy 的终止条件/取消策略（规则函数化），并补单测矩阵覆盖

## 4. Phase 2：资源/缓存生命周期集中化（减少漏清理）

- [ ] 4.1 引入集中入口 `on_node_terminal(node_id, ok)`：统一 artifacts release、cache_pool.on_workflow_node_done、emit 等 side effects
- [ ] 4.2 引入 `finalize_commit_or_discard()`：统一 commit/discard，保证异常路径一致，并补回归覆盖

## 5. 规范同步与验收门禁

- [ ] 5.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/workflow-runtime-module-organization/spec.md` 增加 “execution MUST be Controller+State with injected deps” 的要求
- [ ] 5.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 5.3 跑 `just quick-qa-only-py`（或 `just qa`）作为最终验收
