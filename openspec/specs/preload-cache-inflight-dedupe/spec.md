# preload-cache-inflight-dedupe Specification

## Purpose
TBD - created by archiving change c0-preload-cache-inflight-dedupe. Update Purpose after archive.
## Requirements
### Requirement: preload cache MUST dedupe inflight loads without holding locks during load_fn
当多个线程并发请求同一 `source_id` 的 preload 值时，系统 MUST：

- 对同一 `source_id` 的真实 `load_fn()` 执行次数上界为 1（inflight 去重）
- 在执行 `load_fn()` 时 MUST 不持有保护缓存状态的互斥锁（避免外部回调在锁内执行）
- 等待方 MUST 在 inflight 完成后获得一致的结果或一致的异常

#### Scenario: concurrent callers observe one load and the same cached result
- **WHEN** 两个线程同时调用 `get_or_load("src", load_fn)`
- **AND** `load_fn` 返回 `{1: {"value": "x"}}`
- **THEN** `load_fn` MUST 仅被调用一次
- **AND** 两个线程 MUST 均返回相同的 mapping 结果

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
