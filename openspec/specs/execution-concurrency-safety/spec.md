# no-external-callback-under-lock Specification

## Purpose
为执行层的并发安全定义护栏：任何可能触发用户回调（hooks/observers）或外部回调的操作不得在内部互斥锁临界区内执行，避免重入/锁顺序反转导致的死锁。

## Scope

该规范适用于任何“内部使用互斥锁保护状态”的组件，只要其行为可能触发用户回调（hooks/observers），包括：

- 直接调用 `instrumentation.emit(...)`
- 间接调用会触发 hooks/observers 的 helper（例如资源管理器的 `_emit_*` 封装）

本变更的参考实现**至少**覆盖以下两个组件（其它组件可在后续变更中逐步纳入）：

- `WorkflowCachePool`（`src/scalim/execution/workflow_cache_pool.py`）
- `WorkflowResourceManager`（`src/scalim/workflow/resources.py`）
## Requirements
### Requirement: instrumentation emit MUST NOT run under internal locks
当组件在内部使用互斥锁保护状态时（例如 cache pools、workflow resources 等），系统 MUST 禁止在持锁期间执行：

- `instrumentation.emit(...)`
- 任何会触发 hooks/observers 的回调路径

系统 MUST 将这类外部回调移动到锁外执行（锁内仅采集必要字段与完成状态更新）。

#### Scenario: hook reentrancy does not deadlock
- **GIVEN** 调用方注册了一个 hook/observer，其回调会重入触发同一组件的 API
- **WHEN** 组件触发某个可观测事件（例如 diagnostic warning / resource write）
- **THEN** 系统 MUST 不发生死锁
- **AND** 组件的状态更新 MUST 仍保持一致性（事件在状态更新之后发射；事件 payload/meta 基于锁内快照构造）

### Requirement: lock-safe emit MUST also be thread-safe for observers by default

系统 MUST 同时满足两条约束：
- 回调必须在锁外（避免死锁）
- 锁外回调在并发下必须默认安全（避免并发调用 observer 导致竞态）

系统 MUST 通过 capture+replay 或等价的序列化策略实现上述双约束.

#### Scenario: lock-safe emit does not introduce observer races
- **GIVEN** workflow 并发执行且 emit 在锁外
- **WHEN** 同一个 observer 可能被多个线程触发
- **THEN** 系统 MUST 通过序列化/回放避免并发回调
