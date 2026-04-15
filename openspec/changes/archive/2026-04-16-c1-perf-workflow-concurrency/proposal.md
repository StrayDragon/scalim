## Why

真实业务 workflow（多 demand、DB I/O 重、且希望开并发）中，`max_concurrency>1` 经常出现“越并发越慢、内存显著上涨”的反直觉现象。

除 DB 连接池争抢/IO 抢占外，一个常见放大器是：workflow 并发路径为了默认保证 observers/hooks 的线程安全，会采用 **capture + replay**（单线程回放）策略；但当前捕获阶段可能把 `loader_call` 的 **完整 result** 作为事件 payload 记录在内存中，从而把“本应按批次生命周期释放”的大对象延长为“整次 run/整次 workflow 常驻”，导致内存膨胀、GC 压力升高与整体耗时上升。

同时，调用侧缺少足够细粒度的 per-run 并发策略调参入口：`parallel_mode/max_workers` 只能全局设置，难以针对重 demand 与轻 demand 做差异化控制，迫使下游用手写调度/拆 workflow 等方式绕开框架，破坏可维护性。

## What Changes

- **Perf**：在 workflow 并发（需要 capture+replay）模式下，系统将默认对 `loader_call` 的 captured payload 做“瘦身”（例如以 `type/size` 摘要替代完整 result），避免把大 mapping/list 等对象长期保活在捕获队列中。
  - 目标：在不改变执行正确性的前提下，显著降低 capture+replay 带来的额外内存与时间开销，使 `max_concurrency>1` 更可用。
- **API（增量）**：扩展 `run_workflow(..., run_options_patches_by_run_id=...)` 的 typed patch 能力，允许 per-run 覆盖与继承以下并发相关 runtime knobs：
  - `parallel_mode`（`seq|adaptive`）
  - `max_workers`（`adaptive` 并发上限提示，`0=auto`）
  - 用途：在同一个 workflow 中对不同 run 做差异化策略（例如重 IO run 使用 `seq`，其余 run 使用 `adaptive` 且限制 `max_workers`），避免“全局开并发”带来的 DB 争抢与内存尖峰。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `observer-concurrency-contract`: 补充/收紧 workflow 并发下 capture+replay 的性能护栏，明确 `loader_call` captured payload 的默认策略（避免保活完整 result）。
- `workflow-run-patches`: 扩展 per-run patch 覆盖面，支持 `parallel_mode/max_workers` 的 inherit/override 语义，并保持安全边界字段不可被 patch。

## Impact

- **代码影响面**：
  - workflow 并发执行与 capture+replay：`src/scalim/workflow/execute.py`、`src/scalim/execution/run_ir.py`
  - per-run patch 合并与类型：`src/scalim/dsl/yaml_dsl/workflow_types.py`、`src/scalim/dsl/yaml_dsl/workflow_entrypoints.py`
- **行为影响**：
  - 并发模式下（capture+replay）`loader_call` 的事件 payload 将更轻量；若调用侧依赖“在并发模式下拿到 loader 完整 result 作为事件 payload”，需要调整为串行运行或改用更适合的诊断手段。
