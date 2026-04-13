## Why

c90 完成了 Phase 0（引入 `WorkflowRunController`/`WorkflowRunState`，搬迁逻辑不改行为），但 `execute.py` 仍然承载了准备、编译桥接、资源 commit/discard、viz 快照写入、replay 等多项职责（整文件 `pragma: allow-c901-file`）。Phase 1 的目标是抽离纯函数/规则模块以降低复杂度。

同时需要平衡可维护性和性能（内存占用/CPU）——拆分不应引入不必要的对象分配或间接调用开销。

## What Changes

**Phase 1a：抽离纯函数模块（零运行时开销）**

- `OutcomeBuilder`：异常/结果 → `WorkflowRunOutcome` 映射逻辑（纯函数，不持有状态）。
- `SchedulerRules`：failure_policy 终止条件/取消策略（规则函数，不持有状态）。

**Phase 1b：轻量生命周期封装（最小分配开销）**

- `WorkflowResourceLifecycle`：封装 commit/discard 流程，确保异常路径一致。构造时仅接收引用，不拷贝。
- `WorkflowVizReporter`：封装 viz snapshot 写入和 child replay 链接修复。同上。

**不做的事（守住性能底线）**

- 不引入抽象基类层或策略模式——直接函数调用。
- 不改变数据流向或增加序列化/反序列化。
- 不在热路径上增加额外 dict/list 分配。

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- 核心文件：`src/scalim/workflow/execute.py`、`src/scalim/workflow/execute_controller.py`。
- 新增文件（预估）：`src/scalim/workflow/outcome_builder.py`、`src/scalim/workflow/scheduler_rules.py`。
- `execute.py` 行数预计减少 30-40%。
- 性能：纯函数提取零开销；生命周期封装仅增加引用传递（无拷贝）。
