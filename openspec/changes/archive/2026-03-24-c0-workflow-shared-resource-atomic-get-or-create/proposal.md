## Why

workflow 的共享输出资源（`csv/workbook/sheetbook`）允许多个 nodes 写入同一资源,并要求写入确定性与互斥/串行化（参见 `workflow-shared-output-containers` 与 `workflow-sheetbook-resources`）。

当前 runtime 的 `_get_or_create_*` 模式在并发首次命中同一资源时不是原子操作：可能导致
- 同一 workflow 内被误判为“并发写者”而 fail-fast（`csv/workbook` 写锁被重复尝试获取）
- `sheetbook` 在并发下出现 plan 覆盖,导致写入被静默丢失

这类问题通常只在 CI/高并发/抖动环境出现,回归定位成本高,且与规范的确定性/冲突安全要求不一致。

## What Changes

- 将 workflow 资源管理器的“首次创建 plan +（必要时）获取写锁 + 注册 plan”流程改为对同一 `resource_id` 原子且可 join：
  - 同一 workflow 执行内并发写同一资源时,所有写入 MUST 汇聚到同一个 plan
  - `csv/workbook` 的写锁获取 MUST 只发生一次（供该 workflow 内共享）,避免误报并发写者
  - `sheetbook` plan 创建 MUST 不可被并发覆盖（不得丢写）
- 增加回归测试覆盖上述并发首次命中场景,防止未来回归。
- 补充/加固增量规范中的场景,使其可测试并明确“不依赖完成时序”。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `workflow-shared-output-containers`: 加固共享资源写入的确定性/串行化要求,覆盖并发首次命中同一资源时的 join 行为（不得误报并发写者、不得丢写）。
- `workflow-sheetbook-resources`: 加固对同一 sheetbook 并发写入的互斥/串行化要求,覆盖并发首次创建 plan 的原子性与确定性。

## Impact

- 受影响实现（预期）：
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_csv.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_workbook.py`
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources_sheetbook.py`
- 回归测试重点：并发/线程调度抖动下的稳定性（避免 `time.sleep` 触发的 flaky）。
- OpenSpec 治理：增量规范位于 `openspec/changes/c0-workflow-shared-resource-atomic-get-or-create/specs/**/spec.md`,归档后需同步至 `openspec/specs/*/spec.md` 并通过 `just openspec-check`。

