## Context

- workflow 允许多个 nodes 写入同一个共享资源（`csv/workbook/sheetbook`）,并要求对同一资源的写入互斥/串行化且确定性（声明顺序为 SSOT）。
- 当前实现的 `_get_or_create_*` 采用“先检查 dict → 释放锁 →（可选）获取写锁 → 再写回 dict”的模式。在并发首次命中同一资源时：
  - `csv/workbook` 可能重复获取写锁并误报并发写者（同一 workflow 内也会 fail-fast）
  - `sheetbook` 可能出现并发创建 plan,后写入 dict 的覆盖先写入的 plan,导致丢写

## Goals / Non-Goals

**Goals:**
- 对同一 `resource_id` 的 plan 创建在同一 workflow 执行内 MUST 原子且可 join（并发首次命中只产生一个 plan）。
- `csv/workbook` 写锁获取 MUST 与 plan 绑定且只发生一次,并对同一 workflow 内共享。
- 保持既有写入确定性：写入顺序仍由 workflow YAML 声明顺序决定,不依赖线程完成时序。

**Non-Goals:**
- 不改变跨 workflow/跨进程的并发写入语义（写锁仍用于防止外部并发写同一路径）。
- 不引入新的线程池/并发模型或改变既有 `writes` 编译语义。

## Decisions

1) 原子 get-or-create 的同步策略
- `sheetbook`: plan 创建不涉及 I/O,可在持有全局 `_lock` 的临界区内完成创建并注册,保证原子性。
- `csv/workbook`: 写锁获取可能涉及文件系统操作,不应在持有全局 `_lock` 时长时间阻塞。推荐采用“placeholder + Event/Condition join”模式：
  - 第一个线程在 `_lock` 内注册 placeholder（表示 inflight 创建）
  - 释放 `_lock` 后获取写锁并完成 plan 创建
  - 再在 `_lock` 内替换 placeholder 为最终 plan 并唤醒等待者
  - 等待者在观察到 placeholder 后等待其完成,并返回同一 plan
- 关键要求：异常路径必须唤醒等待者并清理 placeholder,避免死锁。

2) 失败语义
- 若写锁获取失败或 plan 创建失败,系统应 fail-fast；等待者必须得到同样的错误结果（或可诊断的 join 失败信息）。

3) 规范与测试
- 在增量规范中添加可测试的并发场景（“并发首次命中同一资源时 join 成功且无丢写”）。
- 测试实现避免 `time.sleep()` 驱动并发,优先使用 `Event/Barrier` 明确同步点,并设置足够的 timeout 以降低 CI 抖动。

## Risks / Trade-offs

- [死锁风险] placeholder/join 实现若异常路径未正确唤醒,会导致等待者卡死 → 通过 `try/finally` 清理 + 单测覆盖异常路径缓解。
- [复杂度] 原子 join 逻辑较当前实现复杂 → 通过封装共用 helper（csv/workbook 共享）降低重复。
- [行为差异] 之前误报并发写者的场景将变为正常 join → 这是对既有规范语义的纠偏,不视为破坏性变更。

