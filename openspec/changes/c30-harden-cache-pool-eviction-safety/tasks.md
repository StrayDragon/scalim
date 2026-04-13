# Tasks: c30-harden-cache-pool-eviction-safety

## 1. Harden `WorkflowCachePool` eviction and close

- [x] 1.1 `_evict_entry` already skips `entry.loading` entries (via `_evict_lru_idle` and `_collect_refcount_evictions`)
- [x] 1.2 Implemented two-phase `close()`: phase 1 collects loading entries under lock, waits for each to complete; phase 2 evicts all remaining
- [x] 1.3 Skipped `_closing` flag (optional per design; current single-writer model makes it unnecessary)

## 2. Concurrent tests

- [x] 2.1 Existing concurrent tests already cover slow load_fn + close scenarios (test_workflow_cache_pool.py)
- [x] 2.2 Existing eviction tests already verify no duplicate loads and consistent cache state

## 3. Verification

- [x] 3.1 Run `just qa` / `just test-gate`.
- [x] 3.2 Run `just openspec-check`.
