## Context

c90 Phase 0 完成了 `WorkflowRunController`/`WorkflowRunState` 的引入和逻辑搬迁。`execute.py` 仍然是一个 `pragma: allow-c901-file` 的巨石模块。Phase 1 目标是抽离纯函数/规则模块，在**不增加运行时开销**的前提下降低复杂度。

约束：
- 不改变行为
- 不增加对象分配/内存开销（纯函数提取）
- 保持 Python 3.6 兼容
- 逐步可回滚

## Goals / Non-Goals

**Goals:**
- 抽离 `OutcomeBuilder`、`SchedulerRules` 为纯函数模块
- 轻量封装 `WorkflowResourceLifecycle`、`WorkflowVizReporter`
- `execute.py` 行数减少 30-40%

**Non-Goals:**
- 不引入抽象基类/策略模式/插件架构
- 不做 Phase 2（资源/缓存生命周期集中化）——留给后续 change

## Decisions

### 1) Phase 1a：纯函数模块

**`outcome_builder.py`（纯函数，无状态）：**
- `build_outcome_from_exception(exc, node_id, ...) -> WorkflowRunOutcome`
- `build_outcome_from_result(result, node_id, ...) -> WorkflowRunOutcome`
- `safe_error_type(exc) -> str`
- `safe_error_message(exc) -> str`

从 `execute_controller.py` 的 `process_completed_future` 中提取。纯函数调用零分配开销。

**`scheduler_rules.py`（纯函数，无状态）：**
- `should_cancel_on_failure(failure_policy, failed_outcome) -> bool`
- `can_schedule_more(submitted_count, max_concurrency) -> bool`
- `pick_next_node(ready_queue, submitted, ...) -> Optional[str]`

从 `submit_ready_nodes` 的分支逻辑中提取。规则函数化后易于矩阵测试。

### 2) Phase 1b：轻量生命周期封装

**`WorkflowResourceLifecycle`（仅持有引用）：**

```python
class WorkflowResourceLifecycle:
    def __init__(self, resource_manager, artifacts_dir, cache_pool):
        self._rm = resource_manager      # 引用，不拷贝
        self._artifacts = artifacts_dir   # 引用，不拷贝
        self._cache_pool = cache_pool     # 引用，不拷贝

    def on_node_terminal(self, node_id, ok):
        """统一释放 artifacts、cache_pool、emit 等。"""
        ...

    def commit_or_discard(self, success):
        """统一 commit/discard，异常路径一致。"""
        ...
```

构造开销：3 个属性赋值。运行时开销：一次方法调用 vs 当前的内联代码，CPU 差异可忽略。

**`WorkflowVizReporter`（仅持有引用）：**
- `write_snapshot(state, output_path)`
- `fix_child_replay_links(replays, parent_run_id)`

### 3) 内存/CPU 影响分析

| 改动 | 内存 | CPU |
|------|------|-----|
| 纯函数模块 | 0（模块级函数，无实例） | 函数调用开销 ~50ns，可忽略 |
| 生命周期封装 | 每个 ~64 bytes（3 引用 + 对象头） | 方法调用 vs 内联，~50ns 差异 |
| 总计 | < 200 bytes / workflow run | 不可测量 |

### 4) 迁移策略

逐步替换：先提取函数/类到新模块，然后在 `execute_controller.py` 中替换调用，最后删除旧代码。每步可独立 review/回滚。

## Risks / Trade-offs

- 迁移期间可能短暂存在"新模块 + 旧内联代码"的双重存在，通过 task 粒度控制。
- 纯函数提取后，`execute_controller.py` 对新模块产生 import 依赖——可接受（都是 `workflow/` 内部）。

## Migration Plan

- Step 1: 创建 `outcome_builder.py` 并迁移
- Step 2: 创建 `scheduler_rules.py` 并迁移
- Step 3: 创建 `WorkflowResourceLifecycle` 并迁移 on_node_terminal / commit_or_discard
- Step 4: 创建 `WorkflowVizReporter` 并迁移 viz 相关代码
- 每步后运行 `just test-gate` 验证

## Open Questions

- 无。
