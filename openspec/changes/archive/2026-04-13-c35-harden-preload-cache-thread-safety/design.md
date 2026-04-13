## Context

`PreloadCache` 使用 per-source `threading.Lock` + `threading.Event` 实现单次加载去重。两个线程安全隐患在 CPython GIL 下被遮蔽，但在 free-threaded Python 下会暴露。

约束：
- 仅使用内存锁
- 保持 Python 3.6 兼容
- 不影响热路径性能

## Goals / Non-Goals

**Goals:**
- 修复 inflight 状态的无锁读取
- 修复 `MutableMapping` 迭代的线程安全
- 为 free-threaded Python 做前瞻准备

**Non-Goals:**
- 不改变 `PreloadCache` 的 API 或缓存策略
- 不改变 pickle 行为

## Decisions

### 1) Waiter 路径在锁内读取 inflight 状态

当前 waiter 路径（`get_or_load` 中等待者）：
```python
inflight.done.wait(timeout=...)
# 然后无锁读取 inflight.error / inflight.value
```

修改为：
```python
inflight.done.wait(timeout=...)
with lock:
    if source_id in self._data:
        return self._data[source_id]
    if inflight.error is not None:
        raise ...
    return inflight.value
```

这确保所有读取在锁保护下进行。实际上 `_data` 的读取已经在锁内（现有代码 230-232），只是 fallback 到 `inflight.*` 时不在锁内。修复只需将 fallback 也放入锁内。

### 2) `__iter__` / `__len__` 加锁

```python
def __iter__(self):
    with self._global_lock:
        return iter(list(self._data.keys()))

def __len__(self):
    with self._global_lock:
        return len(self._data)
```

使用 `_global_lock`（已存在，用于 `_lock_for`）保护。性能影响可忽略——这些方法不在热路径上。

### 3) 文档注释

在类 docstring 中添加线程安全契约说明。

## Risks / Trade-offs

- `__iter__` 返回快照（`list(keys())`），不是实时视图——但这对 `MutableMapping` 来说是合理的并发语义。
- 增加的锁获取极轻量（`_global_lock` 仅保护 `_lock_for` 查找，现在多保护 `__iter__`/`__len__`）。

## Migration Plan

- 修改 `preload_cache.py`
- 添加并发迭代测试
- 验证：`just test-gate`

## Open Questions

- 无。
