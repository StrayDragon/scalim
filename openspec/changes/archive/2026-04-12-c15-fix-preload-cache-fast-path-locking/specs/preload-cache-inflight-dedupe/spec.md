# preload-cache-inflight-dedupe (delta) Specification

## ADDED Requirements

### Requirement: preload cache hit path MUST be thread-safe under concurrent writers

当同一个 `PreloadCache` 实例被多个线程共享时，系统 MUST 保证 `get_or_load(source_id, ...)` 的 cache hit 读路径在存在并发写入时仍然线程安全：

- 系统 MUST 不以“无锁 membership check + 无锁 index read”的方式访问 `_data[source_id]`
- 系统 MUST 使用与写路径一致的 per-source lock 来保护 “是否命中缓存” 与 “读取缓存值” 的临界区
- 系统 MUST NOT 因并发 dict 变更而在 hit 路径抛出 `KeyError`（或等价的 dict-mutation 竞态异常）

#### Scenario: cache hit does not raise KeyError under concurrent updates
- **GIVEN** 两个线程共享同一个 `PreloadCache`
- **AND** 线程 A 会对同一 `source_id` 的缓存值执行更新/删除（例如 owner 写入 `_data[source_id] = value`，或通过 `__setitem__` / `__delitem__`）
- **WHEN** 线程 B 并发反复调用 `get_or_load(source_id, load_fn)` 且多次命中缓存
- **THEN** 线程 B 的调用 MUST NOT 因 hit 快路径的竞态而抛出 `KeyError`
- **AND** 命中缓存时返回值 MUST 为在同步临界区内观测到的缓存值（或在 miss 时按既有 in-flight 去重语义进入 load 路径）

