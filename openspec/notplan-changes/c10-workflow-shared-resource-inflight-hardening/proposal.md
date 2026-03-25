## Why

`workflow` 共享资源（`csv/workbook/sheetbook`）的 joinable get-or-create（见 `src/scalim/workflow/resources_base.py`）在并发首次命中时依赖"owner 线程完成创建并唤醒 waiter"。
在极端 I/O 抖动/文件系统卡顿/线程异常挂起场景下,owner 可能长时间卡在写锁获取或其它创建路径,导致 waiter **无限等待**；此外,`commit_all()/discard_all()` 未显式处理与"首次创建 inflight"并发交错,存在被误用时的语义灰区（例如 commit 看到空 plans 而提前返回）。

这些问题通常只在 CI/高并发/抖动环境暴露,但一旦发生会表现为"无诊断卡死"或"行为不确定",回归定位成本高。

## What Changes

- 为 joinable get-or-create 引入可选的 **wait diagnostics**（例如 warn-after / repeat-every）,使 waiter 等待过程可观测且可定位（参考 `PreloadCache` 的 inflight wait diagnostics 模式,见 `src/scalim/execution/preload_cache.py` 中 `PreloadCacheWaitDiagnostics`）。
- 为 joinable get-or-create 引入可选的 **max wait / fail-fast** 能力：当 owner 创建长期卡住时,waiter 在超时后 MUST 以可诊断的 `WorkflowWriteError` 失败（默认策略可为"仅告警不超时",避免行为变化）。
- 加固 `commit_all()/discard_all()` 与 inflight 的并发交错语义（两种策略二选一,推荐其一作为 SSOT）：
  - **drain**：commit/discard 在开始前 MUST 等待 inflight 创建完成,保证不会"漏 commit / 漏 discard"；
  - **fail-fast**：若检测到 inflight 非空,commit/discard MUST 失败并给出明确错误（提示调用约束被破坏）。
- 增加可复现的回归用例/脚本（不要求纳入默认测试门禁）：覆盖 owner 卡死导致 waiter 等待与 commit/discard 交错两类场景。

## Repro / Scenarios

### Scenario 1: waiter can hang forever if owner stalls during plan creation
在测试中将 `acquire_write_lock()` monkeypatch 成"卡住不返回",并并发触发同一 `resource_id` 的首次命中：

1) 线程 A 调用 `apply_workbook_sheet()`（首次命中 `report`）,进入 plan 创建并卡住  
2) 线程 B 调用 `apply_workbook_sheet()`（同一 `report`）,进入 join 等待  
3) 如果 A 永远不返回,则 B 永远阻塞（当前无 diagnostics/timeout）

### Scenario 2: commit_all() races with inflight first-create
当某个线程正在 inflight 创建 plan（尚未注册进 `_workbooks/_csvs/_sheetbooks`）时,另一个线程调用 `commit_all()`：

- `commit_all()` 可能观察到空 plans 并提前返回
- 随后 inflight 创建完成,plan 进入容器但本轮 commit 已错过,表现为语义灰区（依赖调用方是否会再次 commit）

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `workflow-shared-output-containers`: 增加 joinable get-or-create 的 liveness/diagnostics 与 commit/discard 与 inflight 并发交错的规范化语义（drain 或 fail-fast 之一）。

## Impact

- 受影响实现（预期）：
  - `src/scalim/workflow/resources_base.py`（join wait 与 inflight drain/fail-fast）
  - `src/scalim/workflow/resources_csv.py`
  - `src/scalim/workflow/resources_workbook.py`
  - `src/scalim/workflow/resources_sheetbook.py`
- 受影响测试/验收（预期）：
  - 新增"可控卡住 + watchdog"的复现脚本或隔离测试（避免引入默认门禁的 hanging 风险）
  - 若引入 warn-after,需确认不会污染正常输出（建议走 instrumentation event 或可控 warning）

## Calibration Notes (2026-03-25)

- 路径已从旧的 `src/scalim/dsl/by_yaml/runtime/workflow_resources_*.py` 校正为当前的 `src/scalim/workflow/resources_*.py`
- 资源类型已补充 `sheetbook`（`resources_sheetbook.py`），当前代码中 `_get_or_create_joinable_plan` 仅管理 `_inflight_workbooks` 和 `_inflight_csvs`，sheetbook 尚未使用 inflight 模式但 `commit_all()/discard_all()` 已覆盖
- `PreloadCache` 的 `PreloadCacheWaitDiagnostics`（`warn_after_s`/`repeat_every_s`/`capture_owner_callsite`）已完整实现并归档,可直接作为设计参考
