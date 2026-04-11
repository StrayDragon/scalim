## Meta

- Type: `fix-0`
- Topic: `WorkflowCachePool.get_or_load()` “准备加载”与 eviction 之间的竞态窗口
- Related code:
  - `src/scalim/execution/workflow_cache_pool.py:244`（`get_or_load`）
  - `src/scalim/execution/workflow_cache_pool.py:338`~`:349`（加载在 `entry.lock` 下执行）
  - Eviction 检查：
    - `src/scalim/execution/workflow_cache_pool.py:415`（`entry.loading` 保护 refcount eviction）
    - `src/scalim/execution/workflow_cache_pool.py:456`~`:460`（`entry.loading` 保护 LRU eviction）

## 背景

`WorkflowCachePool` 的目标是：在 workflow 多节点执行时，对相同 logical key / signature 的 loader 结果进行复用，避免重复加载，并在 refcount=0 或 over-budget 时做可控 eviction。

该模块同时存在：

- 全局锁 `self._lock`：保护 entries/索引结构；
- 每条目锁 `entry.lock`：保护实际加载过程与 `entry.value`。

这是合理的“粗细锁”组合，但当前实现存在一个小窗口：**当某条目需要加载（miss）时，`entry.loading=True` 的标记发生在释放全局锁之后**。在极端并发/异常路径下，可能导致条目在“准备加载但尚未标记 loading”时被 eviction。

## 现状（关键路径）

`get_or_load` 结构（简化）：

1) `with self._lock:` 取/建 `entry`，记录 acquire event；  
2) 释放全局锁后 emit events；  
3) `with entry.lock:`  
   - 若已有 value 直接返回；  
   - 否则 `entry.loading = True`，调用 `load_fn()`，写入 `entry.value`，finally `entry.loading=False`。

问题点：在步骤 1 与步骤 3 之间存在窗口：

- `entry.value is None`
- `entry.loading` 仍可能为 `False`（尤其是“已有 entry 但 value 为空”的情况）
- 其他线程可以在全局锁下进行 eviction，并以 `entry.loading` 作为“是否可 evict”的保护条件

## 触发条件与影响

### 触发条件（典型）

最容易出现“已有 entry 但 value 为空”的路径是：`load_fn()` 抛异常。

- 当 owner load 失败时，`entry.value` 仍为 `None`，且 finally 会把 `entry.loading` 置回 `False`；
- 后续重试（同 signature_key）会复用同一个 entry，再次走 miss；
- 重试线程在释放全局锁、进入 `entry.lock` 之前，`entry.loading` 仍是 `False`。

此时如果并发触发 eviction（例如另一个线程在添加新 entry 时触发 over-budget eviction），就可能把该 entry 从 pool 的索引结构中移除。

### 影响

- 语义层面：`get_or_load()` 返回的 value 仍正确（当前线程持有 entry 引用并会完成 load），但 **加载结果可能无法留在 cache_pool 中**（条目已被移除）。
- 性能层面：缓存复用失败，导致重复 load；若 load 有副作用（例如外部服务调用）会放大成本。
- 诊断层面：由于 acquire/release/evict 事件是异步 emit，可能出现“看起来加载成功但又立即 miss”的疑难问题。

## 例子（并发序列）

1) 节点 A：`get_or_load(K)` → `load_fn()` 抛异常 → entry(K) 留在 pool，`value=None, loading=False`  
2) 节点 B：重试 `get_or_load(K)`，离开全局锁准备进入 `entry.lock`  
3) 节点 C：`get_or_load(K2)` 触发 over-budget eviction，在全局锁下扫描 LRU，看到 entry(K) `loading=False` 且满足可 evict 条件，于是 evict entry(K)  
4) 节点 B：进入 `entry.lock`，加载成功并写入 `entry.value`，但 entry(K) 已从 pool 结构中移除 → 下次再取仍 miss

## 目标

- “准备加载”的条目在 load 完成前不应被 eviction；
- 不降低并发度（避免长时间持有全局锁）；
- 保持 Python 3.6 兼容；
- 行为不改变（除了修复竞态导致的缓存丢失）。

## 推荐修复方案

### 方案 A：在释放全局锁前建立“loading 意图”标记（推荐最小改动）

做法：

- 在 `with self._lock:` 中，如果判定当前调用需要走 miss（`entry.value is None`），则在释放全局锁前就设置 `entry.loading=True`（或设置一个新的 `entry.inflight=True` 标志）。
- 真实 load 仍在 `entry.lock` 下执行；finally 置回 `loading=False`。

关键点：

- 该标志的意义是“避免 eviction”，不是“保证只有一个 loader”（单 loader 仍由 `entry.lock` 保证）。

优点：

- 改动小；
- 能直接消除 eviction 竞态窗口；
- 不需要改变现有锁顺序（仍然是全局锁 → 释放 → entry.lock）。

缺点：

- `entry.loading` 变成“跨锁域”状态：在没有 `entry.lock` 的情况下就写入该字段，理论上会让读者担心一致性（但它只用于 eviction gate，且 eviction 也在全局锁下读它）。

### 方案 B：调整锁顺序：全局锁内先获取 `entry.lock`（语义更强，但可能阻塞）

做法：

- `with self._lock:` 拿到 entry 后，在释放全局锁之前尝试 `entry.lock.acquire()`；
- 在持有 entry.lock 后再释放全局锁，执行 load。

优点：

- `entry.loading` 的写入与实际 load 更一致（都在 entry.lock 下）。

缺点：

- 可能在持有全局锁时等待 entry.lock，导致全局锁竞争变大；
- 需要非常小心地保证不会形成反向锁顺序（目前 eviction 不拿 entry.lock，风险较小，但仍需明确约束）。

### 建议额外改进（可选，但强烈建议纳入 fix-0）

- 在 `load_fn()` 抛异常时，考虑从 pool 中移除该 entry（或记录 error 并提供重试策略），避免“value=None 的 entry 常驻”放大问题与复杂度。

## 性价比

- 方案 A：高（最小改动修掉竞态，符合 fix-0 定位）。
- 方案 B：中（语义更强但可能引入性能/锁竞争风险）。

## 验证建议（测试口径）

- 新增并发测试（可放在 `tests/execution/`）：
  - 构造一个 entry 首次 load 失败、第二次重试；
  - 并发触发 `over_budget eviction` 或 `refcount eviction`；
  - 断言：重试成功后条目仍存在于 pool，后续 get_or_load 为 hit（或至少不会因为 eviction 丢失）。
- 运行 `just quick-qa-only-py` 作为回归。

