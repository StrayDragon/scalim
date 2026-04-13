# workflow-cache-pool-safety Specification

## Purpose
TBD - created by archiving change c30-harden-cache-pool-eviction-safety. Update Purpose after archive.
## Requirements
### Requirement: `WorkflowCachePool.close` MUST synchronize with in-flight loads

`WorkflowCachePool.close()` MUST 在逐出或销毁条目之前，等待当前处于 `loading=True` 的条目完成加载（成功或失败），以避免关闭路径与 `load_fn` 并发导致的孤儿条目、重复加载或关闭后仍运行的后台加载。

- 等待逻辑 MUST 在获取 `entry.lock` 时与 `get_or_load` 的锁顺序一致：不得在持有全局 `self._lock` 的同时获取 `entry.lock`（与现有 `get_or_load` 约定一致），以避免死锁。
- 等待 MAY 带超时；若采用超时，行为 MUST 可诊断（例如明确错误或日志），且测试 MUST 覆盖正常完成路径。

#### Scenario: close waits for slow load

- **GIVEN** 某缓存条目的 `load_fn` 被 `threading.Event` 人为延长执行时间
- **WHEN** 另一线程在加载进行中调用 `close()`
- **THEN** `close()` MUST 等待该加载完成（在无限等待或文档化超时语义下）后再完成清理
- **AND** 不得留下对已逐出条目的写入或同一 key 的重复加载

### Requirement: LRU / refcount eviction MUST skip loading entries

`_evict_entry` 及由预算/refcount 触发的淘汰路径 MUST 跳过 `entry.loading` 为真的条目；该行为 MUST 与关闭路径协同，保证不会在加载持有 `entry.lock` 期间从 `_entries` 移除该条目。

#### Scenario: eviction does not orphan a loading entry

- **GIVEN** 某 signature 的条目处于 in-flight load（`loading=True`）
- **WHEN** 并发触发 LRU 或 refcount 驱动的逐出
- **THEN** 逐出逻辑 MUST NOT 将该条目从池中移除以致加载结果写入孤儿对象
- **AND** 加载完成后状态 MUST 与池内元数据一致

### Requirement: Concurrent safety MUST be covered by tests

系统 MUST 在 `tests/workflow/test_workflow_cache_pool.py`（或等价模块）中提供并发回归用例，至少覆盖：

- 加载进行中调用 `close()` 时，关闭与加载的交互符合上述要求。
- eviction 与对同一 key 的并发 `get_or_load` 不产生重复加载或缓存不一致。

#### Scenario: regression tests protect close vs load race

- **WHEN** 运行默认非 bench 测试套件中的 workflow cache pool 并发用例
- **THEN** 用例 MUST 通过并锁定上述安全语义

### Requirement: Optional `_closing` flag MUST not weaken documented API semantics

若实现引入 `_closing`（或等价）标志以使 `close()` 之后的新 `get_or_load` 快速失败，该行为 MUST 与现有对外 API 文档及错误语义一致，且 MUST 具备测试覆盖。

#### Scenario: new loads after close are rejected consistently

- **GIVEN** `close()` 已设置关闭状态（若采用 `_closing`）
- **WHEN** 调用方在关闭后尝试 `get_or_load`
- **THEN** 系统 MUST 以满足文档的方式失败（例如明确异常类型/消息），而不得静默返回陈旧或部分初始化的条目

