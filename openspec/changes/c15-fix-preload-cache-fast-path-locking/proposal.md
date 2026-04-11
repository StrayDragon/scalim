## Meta

- Type: `fix-0`
- Topic: `PreloadCache.get_or_load()` 无锁 fast-path 读 `_data` 的线程安全语义修正
- Related code:
  - `src/scalim/execution/preload_cache.py:326`~`:366`（`get_or_load`）
  - Fast-path：`src/scalim/execution/preload_cache.py:334`~`:335`
  - 写路径：`src/scalim/execution/preload_cache.py:209`~`:216`（owner 写入 `_data[source_id] = value`）

## 背景

`PreloadCache` 的文档与设计目标明确写了“线程安全的 preload_forever 缓存容器”（见 `src/scalim/execution/preload_cache.py:111` 起注释）。

在这种语义下，调用方自然会假设：

- 多线程并发调用 `get_or_load` 是安全的；
- cache hit 路径也不会出现竞态异常或读到不一致状态。

当前实现为了性能在 `signature_guardrail` 关闭时加入了一个 fast-path：

```py
digest = self._guardrail_digest_or_none(...)
if digest is None and source_id in self._data:
    return self._data[source_id]
```

这段读路径未加 per-source lock。

## 现状与问题

### 问题点

在 Python/CPython 中，“并发读 dict”通常没问题，但“并发读 + 写 dict”不承诺线程安全。

当前 `PreloadCache` 的写路径（owner load 完成后）会在 per-source lock 下执行：

- `self._data[source_id] = value`

而 fast-path 读路径在不持锁的情况下：

- 做 `source_id in self._data`（读）
- 再 `self._data[source_id]`（读）

这与并发写组合在一起，会出现“逻辑竞态窗口”。在极端情况下可能导致：

- `KeyError`（成员检查与索引读取之间被删除/替换）
- 读到旧值/未完成更新的状态（语义上不严格）
- “线程安全”契约被破坏，引发测试/生产偶现问题

即使在大多数情况下 CPython 的 GIL 让问题不明显，这仍属于不必要的风险点：尤其 `PreloadCache` 已经以“线程安全容器”定位，最好让实现与定位一致。

## 触发例子（思路）

- 线程 A：刚写入/删除 `self._data[source_id]`（通过 `__setitem__`/`__delitem__` 或 owner load 路径）
- 线程 B：命中 fast-path，在 `source_id in self._data` 与 `self._data[source_id]` 间发生切换

这类问题通常在：

- CI 高负载 + 并行（xdist）；
- 或业务运行时多线程抢占严重；

更容易暴露。

## 目标

- 让 `PreloadCache` 的 cache hit 读路径也满足线程安全语义；
- 行为保持不变（仍然按 source_id 去重、inflight 等语义不变）；
- Python 3.6 兼容。

## 推荐修复方案

### 方案 A：移除无锁 fast-path，所有读写统一走 per-source lock（推荐）

做法：

- 删除 `if digest is None and source_id in self._data: return ...` 的无锁路径；
- 统一通过 `lock = self._lock_for(source_id)` 并在 `with lock:` 下检查/返回 cached。

优点：

- 语义最清晰：所有对 `_data[source_id]` 的访问都在同一把锁下；
- 最符合“线程安全容器”的定位；
- 回归风险低（只影响性能与极端竞态）。

缺点：

- cache hit 多时会增加一次锁开销；
- 但 `get_or_load` 通常按 source_id 维度调用（不是每行/每字段），锁开销相对 load_fn 成本很小。

性价比：

- 高（fix-0 级别的确定性收益）。

### 方案 B：保留 fast-path 但改成“乐观读取 + 回退持锁”（不推荐）

做法：

- 先尝试无锁 `dict.get`，若 miss 再加锁；
- 或捕获 `KeyError` 并回退持锁路径。

缺点：

- 仍然是“依赖 CPython 实现细节”的优化；
- 复杂度增加，收益有限，容易在未来维护中出错。

## 验证建议（测试口径）

- 新增一个并发压力测试：
  - 多线程对同一 source_id 并发 `get_or_load`；
  - 同时穿插 `__setitem__` / `__delitem__` 或触发 owner load 写入；
  - 断言不出现 `KeyError`，且语义正确。
- 跑 `just quick-qa-only-py`。

