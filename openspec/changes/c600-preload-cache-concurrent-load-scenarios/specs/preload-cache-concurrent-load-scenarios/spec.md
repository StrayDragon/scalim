# preload-cache-concurrent-load-scenarios Specification

## Purpose
将 `cache_mode=preload_forever` 相关的并发边界与“同一个 load”的定义文档化：在何种场景下可能发生并发请求、key 是什么、默认语义只承诺 in-flight 去重（而非跨进程/跨不同 signature 的全局去重），并提供可复现的最小样例。

## ADDED Requirements

### Requirement: concurrency scenarios MUST be explicit and reproducible
系统 MUST 明确并提供可复现的说明，至少覆盖：

- 多线程并发多个 `ScalimEngine.run()` 且共享同一个 `preloaded_cache`（当 `preloaded_cache` 提供 `get_or_load` 时，应按 key 做 in-flight 去重）
- workflow 多节点并发请求同一 `WorkflowCachePool` signature（同一 signature 同一时刻最多一个实际 `load_fn` 运行）

系统 MUST 明确默认语义仅为 **in-flight 去重**，不承诺跨进程去重。

#### Scenario: two concurrent callers trigger at most one in-flight load per key
- **GIVEN** 两个并发执行单元（线程或 workflow node）请求同一缓存 key（`source_id` 或 signature）
- **WHEN** 该 key 当前为 miss
- **THEN** 系统 MUST 保证同一时刻最多一个实际 `load_fn` 被执行
- **AND** 其余请求 MUST 等待并复用该次 load 的结果或异常
