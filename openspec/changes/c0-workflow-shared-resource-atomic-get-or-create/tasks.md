## 1. Specs / Scenarios

- [ ] 1.1 补齐并校验本 change 的增量规范：`openspec/changes/c0-workflow-shared-resource-atomic-get-or-create/specs/**/spec.md`（覆盖并发首次命中同一资源时 join 且无丢写的场景）。
- [ ] 1.2 运行 `openspec validate --change c0-workflow-shared-resource-atomic-get-or-create --strict --no-interactive` 确保结构与格式正确。

## 2. Runtime Fix

- [ ] 2.1 修复共享 `csv/workbook` 的 `_get_or_create_*`：对同一 `resource_id` 原子创建并 join,写锁获取只发生一次且供同一 workflow exec 内共享。
- [ ] 2.2 修复共享 `sheetbook` 的 `_get_or_create_*`：确保并发首次命中不产生多个 plan/不覆盖,避免丢写。
- [ ] 2.3 为异常路径补齐清理/唤醒逻辑,避免 join 等待者死锁。

## 3. Regression Tests / Gates

- [ ] 3.1 新增回归测试覆盖并发首次命中场景（避免 `time.sleep` 驱动,使用 `Event/Barrier` 明确同步点）。
- [ ] 3.2 通过门禁：
  - `just openspec-check`
  - `just qa`

