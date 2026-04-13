## Context

`WorkflowCachePool` 使用两层锁：全局 `self._lock`（元数据/LRU/引用计数）和 per-entry `entry.lock`（保护实际加载）。`_evict_entry` 在全局锁内操作但不获取 `entry.lock`，导致正在加载的条目可被驱逐。

当前工作流生命周期下（`close()` 在所有 futures 完成后调用）风险较低，但在测试复用、未来并发扩展中是真实缺陷。

约束：
- 仅使用内存锁，不引入文件锁
- 不改变缓存池的外部 API
- 保持 Python 3.6 兼容

## Goals / Non-Goals

**Goals:**
- 消除 eviction/close 与 loading 的竞态
- 增加并发安全测试

**Non-Goals:**
- 不改变 LRU/引用计数驱逐策略
- 不改变缓存池的容量/预算配置

## Decisions

### 1) eviction 跳过 loading 条目（已部分实现），close 等待 loading 完成

当前 `_evict_entry` 检查 `entry.loading` 但仍可在 `close()` 中被调用。改进：

**`_evict_entry`：** 保持现有 `entry.loading` 跳过逻辑。

**`close()`：**
```python
def close(self) -> None:
    # Phase 1: 等待所有 loading 条目完成
    with self._lock:
        loading_entries = [e for e in self._entries.values() if e.loading]
    for entry in loading_entries:
        with entry.lock:  # 等待 load_fn 完成
            pass
    # Phase 2: 驱逐所有条目（此时无 loading）
    with self._lock:
        for sig_key in list(self._entries.keys()):
            self._evict_entry(sig_key, ...)
```

**锁顺序安全性：** `entry.lock` 在 `self._lock` 释放后获取（与 `get_or_load` 一致），无死锁风险。

### 2) 可选：`_closing` 标志

在 `close()` 入口设置 `self._closing = True`（在全局锁内），让 `get_or_load` 在 `_closing` 时快速失败。这可以防止 close 与新 load 请求的竞态。

### 3) 并发测试

新增测试场景：
- 模拟 `load_fn` 长时间运行（用 `threading.Event` 控制），在加载期间调用 `close()`，验证 close 等待加载完成。
- 模拟 eviction 与并发 `get_or_load` 同一 key，验证不产生重复加载。

## Risks / Trade-offs

- `close()` 需要等待加载完成，可能增加关闭延迟。但由于工作流结束时所有 futures 已完成，实际 loading 应已结束。
- `_closing` 标志使 API 行为在 close 后不同（抛异常），需文档说明。

## Migration Plan

- 修改 `workflow_cache_pool.py`
- 添加并发测试
- 验证：`just test-gate`

## Open Questions

- 无。
