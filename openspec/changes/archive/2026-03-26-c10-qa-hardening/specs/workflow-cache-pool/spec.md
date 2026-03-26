## ADDED Requirements

### Requirement: cache pool eviction MUST NOT evict in-flight (loading) entries
当 cache pool 条目处于 in-flight load（`loading=True`）时，系统 MUST NOT 将其作为 refcount/LRU 的淘汰候选；否则可能导致条目被逐出后成为“孤儿”，从而触发重复加载与缓存不一致。

#### Scenario: refcount eviction skips loading entries
- **GIVEN** 某个 signature 的缓存条目处于 `loading=True`
- **WHEN** workflow node done 触发 refcount=0 的逐出逻辑
- **THEN** 逐出逻辑 MUST 跳过该条目
- **AND** 后续请求 MUST 复用该次 in-flight load 的结果（不得重复加载）

## Notes
- 该要求用于补齐 “in-flight dedupe” 与 “release/evict” 的协同边界。
