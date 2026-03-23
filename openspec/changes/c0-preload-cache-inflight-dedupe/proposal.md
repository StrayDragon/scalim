## Why

`PreloadCache.get_or_load()` 当前在持有 per-source `Lock` 的情况下执行用户提供的 `load_fn()`（`src/scalim/execution/preload_cache.py`）。这会把“互斥去重”扩大成“互斥执行用户逻辑”，带来两类 c0 风险：

1. **潜在死锁 / 卡死放大器**：`load_fn` 是外部回调，可能直接或间接重入 preload cache（同 key 或锁顺序反转），导致自死锁；或因为 `load_fn` 内部阻塞导致其它线程无限等待同一 key（CI 偶发卡死的典型模式）。
2. **性能与可控性差**：持锁执行用户逻辑会把锁持有时间变为不受控（I/O、网络、第三方库等），不仅影响同 key 的并发等待体验，也使排障更困难（锁争用与真实瓶颈混在一起）。

### 最小复现（单线程自死锁）

以下示例展示“重入同 key”导致的立即自死锁（概念性）：

```py
from scalim.execution.preload_cache import PreloadCache

cache = PreloadCache()

def load():  # noqa: ANN001
    # 真实场景里可能是更隐蔽的间接重入（例如 loader 内部触发另一条 pipeline 访问同一 runtime.preloaded_cache）
    return cache.get_or_load("src", load)

cache.get_or_load("src", load)  # 当前实现会卡死
```

## What Changes

- 将 `load_fn()` 的执行移出锁临界区，同时保持“同一 key 最多一次真实加载”的语义
  - 在锁内建立/查询 “inflight” 状态（例如 `Event/Future/Condition`）
  - 只有第一个线程负责执行 `load_fn()`；其它线程释放锁后等待 inflight 完成，再读取结果
  - 需要定义失败语义：若 `load_fn` 抛异常，等待方应一致地收到异常（并清理 inflight 状态，允许后续重试）
- 增加可诊断性
  - 可选：为 inflight 等待增加超时/诊断（至少在测试中使用 join/wait timeout 防卡死）
- 更新/新增并发回归测试
  - 两线程同时 `get_or_load`，断言 `load_fn` 只执行一次且不会卡死
  - `load_fn` 抛异常时，所有等待方收到同一异常且缓存未写入半成品

> 兼容性说明：这是一项内部并发语义优化；对外 API 与结果不应变化，但可显著降低“偶发卡死”风险并提升整体吞吐。

## Capabilities

### New Capabilities
- `preload-cache-inflight-dedupe`: 定义 preload cache 的 inflight 去重语义（锁粒度、等待/异常传播、以及 pickling 状态约束）。

### Modified Capabilities
- `source-cache`: 补充并发要求：preload cache 的“去重锁”不得覆盖 `loader` 的实际执行；并明确异常传播与重试语义。

## Impact

- 受影响代码路径：
  - `src/scalim/execution/preload_cache.py`（核心实现）
  - `tests/test_preload_cache.py`（并发测试需要与新语义对齐，且应增加防卡死超时）
- 运行时收益：
  - 降低死锁/卡死风险，缩短锁持有时间，提高并发可预测性与性能
