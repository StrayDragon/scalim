# no-external-callback-under-lock Specification

## Purpose
为执行层的并发安全定义护栏：任何可能触发用户回调（hooks/observers）或外部回调的操作不得在内部互斥锁临界区内执行，避免重入/锁顺序反转导致的死锁。

## ADDED Requirements

### Requirement: instrumentation emit MUST NOT run under internal locks
当组件在内部使用互斥锁保护状态时（例如 cache pools、workflow resources 等），系统 MUST 禁止在持锁期间执行：

- `instrumentation.emit(...)`
- 任何会触发 hooks/observers 的回调路径

系统 MUST 将这类外部回调移动到锁外执行（锁内仅采集必要字段与完成状态更新）。

#### Scenario: hook reentrancy does not deadlock
- **GIVEN** 调用方注册了一个 hook/observer，其回调会重入触发同一组件的 API
- **WHEN** 组件触发某个可观测事件（例如 diagnostic warning / resource write）
- **THEN** 系统 MUST 不发生死锁
- **AND** 组件的状态更新 MUST 仍保持一致性（事件在状态更新之后发射）
