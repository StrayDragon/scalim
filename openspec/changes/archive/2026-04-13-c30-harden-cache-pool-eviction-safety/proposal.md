## Why

`WorkflowCachePool._evict_entry` 从 `_entries` 字典中移除条目时**不获取 `entry.lock`**。如果另一个线程已经通过 `get_or_load` 的全局锁区间并持有 `entry.lock` 正在执行 `load_fn()`，驱逐会导致：

1. 被驱逐的 `_CacheEntry` 成为孤儿对象，加载完成后写入已脱离的对象。
2. 新的 `get_or_load` 对同一 `signature_key` 创建新条目 → **重复加载**。
3. `close()` 不等待加载中条目完成，可能在工作流结束后仍有后台加载运行。

虽然在当前单写者控制器模型下（`close()` 在所有 futures 完成后调用）风险较低，但这是一个真实的并发安全缺陷。

## What Changes

- `_evict_entry` 在移除条目前检查 `entry.loading` 并跳过或等待正在加载的条目。
- `close()` 增加"等待所有 loading 条目完成"的逻辑（带超时）。
- 可选：引入 `_closing` 标志，让正在执行 `load_fn` 的线程感知池正在关闭。
- 增加并发测试覆盖：模拟 eviction 与 load 同时发生的场景。

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- 文件：`src/scalim/execution/workflow_cache_pool.py`。
- 纯内存锁增强，不影响用户文件系统。
- 测试：`tests/workflow/test_workflow_cache_pool.py` 增加并发场景。
