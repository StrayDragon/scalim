# workflow-cache-pool (delta) Specification

## MODIFIED Requirements

### Requirement: cache pool eviction MUST NOT evict in-flight (loading) entries

当 cache pool 条目处于 in-flight load(`loading=True`)时,系统 MUST NOT 将其作为 refcount/LRU 的淘汰候选;否则可能导致条目被逐出后成为“孤儿”,从而触发重复加载与缓存不一致.

为避免“准备加载”与 eviction 之间的竞态窗口,系统 MUST 满足:

- 对任何 `get_or_load()` 调用,只要判定该次为 miss(`entry.value is None`)且将进入 load 流程,系统 MUST 在释放全局锁之前将该 entry 标记为 `loading=True`
- 该规则 MUST 覆盖“已有 entry 但 value 为空”的重试路径(例如前一次 `load_fn()` 抛异常后再次重试)
- `loading` MUST 在 load 完成(成功写入 value 或异常退出)后被恢复为 `False`

#### Scenario: refcount eviction skips loading entries
- **GIVEN** 某个 signature 的缓存条目处于 `loading=True`
- **WHEN** workflow node done 触发 refcount=0 的逐出逻辑
- **THEN** 逐出逻辑 MUST 跳过该条目
- **AND** 后续请求 MUST 复用该次 in-flight load 的结果(不得重复加载)

#### Scenario: budget eviction skips loading entries during retry miss window
- **GIVEN** 某 signature 的缓存条目曾因 `load_fn()` 异常而处于 `value=None`
- **AND** 另一线程对该 signature 发起重试 `get_or_load()` 并进入“准备加载”窗口
- **WHEN** 并发触发 over-budget LRU eviction 扫描
- **THEN** eviction MUST 将该条目视为 in-flight 并跳过(不得逐出)
- **AND** 重试 load 成功后,该条目 MUST 仍保留在 cache pool 中以供后续 hit 复用
