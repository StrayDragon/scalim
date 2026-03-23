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

