# Proposal: adaptive-cache-explicit-locks

> 一句话描述: 为 adaptive 并行模式下共享可变缓存结构引入显式锁与 free-threaded 检测，摆脱对 CPython GIL 的依赖并消除 check-then-act 竞态。

## Why

`parallel_mode="adaptive"` 下，`ExecutionRuntime` 中 6+ 个可变 dict/set（`load_ref_cache`、`key_normalize_cache`、`load_ref_group_executed`、`guardrail_logged`、`rows_cache_logged`、`relation_guardrail_stats`）在多个工作线程间无锁共享。

当前实现**显式文档化**了对 CPython GIL 的依赖（`runtime.py:49-51`），并声明 free-threaded/no-GIL Python 不在支持范围内。但随着 Python 3.13+ free-threaded 模式的推进，此技术债务将成为迁移障碍。

即使在 GIL 下，check-then-act 模式（如缓存 miss → 加载 → 写入）也可能导致重复加载/重复 warning。

## What Changes

1. **短期**: 添加运行时 `sys.flags` 检测，若检测到 free-threaded 模式则拒绝 `parallel_mode="adaptive"`（fail-fast）
2. **中期**: 为高频共享结构引入显式锁
   - `load_ref_cache` → per-relation-signature `threading.Lock`（类似 `PreloadCache` 模式）
   - `guardrail_logged` / `rows_cache_logged` → `threading.Lock` 保护的 set
   - `key_normalize_cache` → per-signature lock
3. **长期**: 考虑 per-task 完全隔离 + fan-in 合并（消除共享可变状态）

## Capabilities

### Modified Capabilities

- `execution-concurrency-safety` — 从 GIL 依赖迁移到显式同步
- `parallel-execution` — adaptive 模式并发安全

## Impact

- **代码区域**: `src/scalim/execution/executor/runtime/runtime.py`, `src/scalim/execution/executor/operators/load_ref/`
- **破坏性**: 无（内部实现变更，行为更安全）
- **性能**: 锁引入可能有微小开销，需要基准测试验证
- **时间线**: 中长期项目，与 Python free-threaded 生态同步推进
