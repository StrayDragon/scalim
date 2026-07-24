# Proposal: preloaded-cache-safety-check

## Why

`ScalimEngine` 的 `preloaded_cache` 参数接受 `MutableMapping[str, LoaderResultMapping]`，文档警告"若要跨多个并发 runs 共享缓存，不要共享普通 dict"，但运行时不做任何检查。用户可能意外共享普通 `dict` 导致数据竞争。

`PreloadCache` 是正确的线程安全替代（per-key 锁 + inflight 去重），但 API 未强制使用。

## What Changes

1. **运行时类型检查**：当 `max_concurrency > 1`（workflow）或 `parallel_mode="adaptive"` 时，若 `preloaded_cache` 是普通 `dict`，发出 `UserWarning`
2. **可选自动包装**：提供 `auto_wrap=True` 选项，自动将普通 `dict` 包装为 `PreloadCache`（或文档明确建议使用 `PreloadCache`）
3. **更新 `ScalimEngine` 文档**：在参数说明中强化 `PreloadCache` 的推荐

## Capabilities

### Modified Capabilities

- `execution-preload-cache` — 安全检查增强
- `execution-concurrency-safety` — 并发安全守卫

## Impact

- **代码区域**: `src/scalim/execution/engine.py`, `src/scalim/workflow/execute.py`
- **破坏性**: 无（warning 不中断执行）
- **竞态安全**: 从 High 降为 Low（误用时提供明确警告）
