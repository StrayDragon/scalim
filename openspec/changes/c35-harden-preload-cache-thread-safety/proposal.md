## Why

`PreloadCache` 存在两个线程安全隐患：

1. **无锁读取 inflight 状态**：等待者在 `Event.wait()` 返回后读取 `inflight.error` / `inflight.value` 不持有锁。在 CPython GIL 下实际安全，但在 free-threaded Python (PEP 703 / 3.13t+) 下不正式正确。

2. **`MutableMapping.__iter__`/`__len__` 不安全**：直接访问 `_data` 字典不加锁，并发修改时可能抛异常或跳过元素。

## What Changes

- `get_or_load` 的 waiter 路径：在锁内读取 `inflight.error` / `inflight.value`，或在 `_data` 写入后直接从 `_data` 读取（已在锁内）。
- `__iter__` / `__len__` / `__contains__`：在方法内获取全局锁后操作 `_data` 快照。
- 添加 debug/文档注释说明线程安全边界。
- 增加并发测试：多线程同时 iterate 和 `get_or_load`。

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- 文件：`src/scalim/execution/preload_cache.py`。
- 纯内存锁增强，不影响性能（锁粒度极细）。
- 为 free-threaded Python (3.13t/3.14t) 做前瞻准备。
