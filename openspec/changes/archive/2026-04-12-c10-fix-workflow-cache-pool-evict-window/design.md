## Context

`WorkflowCachePool` 提供 workflow-scope 缓存池,用于在同一次 workflow 执行内跨 nodes 复用相同 logical key/signature 的 loader 结果,并在 refcount=0 或 over-budget 时执行 eviction。

实现采用“粗细锁”组合:

- 全局锁 `self._lock`: 保护 entries/索引结构/LRU 顺序/consumer set 等共享状态
- 每条目锁 `entry.lock`: 保护实际加载过程与 `entry.value` 写入

eviction(包含 refcount eviction 与 LRU over-budget eviction)以 `entry.loading` 作为“是否可淘汰”的关键护栏: `loading=True` 的条目不得被逐出,否则可能形成“条目被逐出但 load 仍在进行”的孤儿状态,导致复用失败与重复 load。

当前竞态窗口出现在 `get_or_load()` 的重试 miss 路径:

- 当某 signature 的 `load_fn()` 失败时,entry 会保留在 pool 中,并回到 `value=None, loading=False`
- 后续重试调用 `get_or_load()` 在释放全局锁后才会进入 `entry.lock`,并在 `entry.lock` 内把 `entry.loading=True`
- 在“释放全局锁 → 获取 entry.lock”之间存在窗口: entry 仍在 pool 中、`value=None` 且 `loading=False`,此时并发 eviction 可能把该 entry 从 pool 的索引结构中移除
- 结果: 重试线程仍能完成 load 并返回正确值,但该值可能无法留在 cache_pool 中(下次仍 miss)

约束与治理:

- 运行时保持 Python 3.6 兼容
- 必须保持 `instrumentation.emit(...)` 在锁外执行(见 `no-external-callback-under-lock` 护栏与现有 reentry 测试)
- OpenSpec/规范为 SSOT: 需要同步 `openspec/specs/workflow-cache-pool/spec.md` 的相关要求并运行 `just openspec-check`

## Goals / Non-Goals

**Goals:**

- 消除 `get_or_load()` 在“准备加载”与 eviction 之间的竞态窗口: 对任何会执行 miss load 的调用,在释放全局锁前建立明确的 in-flight 标记,使 eviction 不可逐出该条目
- 保持并发度: 不在持有全局锁期间执行 `load_fn()` 或等待 `entry.lock`
- 保持事件 emit 的锁外语义不变(避免重入死锁)
- 行为不改变(除了修复竞态导致的缓存丢失/复用失败)

**Non-Goals:**

- 不调整锁顺序为“全局锁内获取 entry.lock”(避免扩大锁竞争与潜在反向锁顺序风险)
- 不在本次引入对 `load_fn()` 异常的“自动删除 entry/错误缓存策略”(该类改动需要更完整的语义与锁顺序设计,可另开 change)

## Decisions

### 1) 在释放全局锁前建立 loading 意图(覆盖 existing miss)

修复采用最小改动方案:

- 在 `with self._lock:` 内完成以下动作:
  - 取/建 `entry`
  - 判定该次调用是否为 miss (`entry.value is None`)
  - 若为 miss,在释放全局锁前设置 `entry.loading=True`(作为 eviction gate)
  - 采集并构造 pending emits(保持 emit 在锁外)

关键点:

- `entry.loading` 的意义在本修复中明确为 “eviction gate: 表示该 entry 在本次调用中处于/即将进入 in-flight load,不得被逐出”
- “单 loader”依旧由 `entry.lock` 保证(同 signature 并发最多一个 `load_fn` 执行)

### 2) 在 entry.lock 内确保 loading 状态不会泄漏

由于 `entry.loading` 可能在全局锁内被提前置为 `True`,在进入 `entry.lock` 后需要覆盖两类路径:

- **hit**: 若 `entry.value is not None`,必须在返回前将 `entry.loading=False`(避免留下“永久 loading”导致后续无法 eviction)
- **miss**: 执行 `load_fn()` 前保持 `entry.loading=True`,并在 finally 中恢复 `entry.loading=False`

该策略保证:

- eviction 在“准备加载窗口”与“实际加载窗口”都能看到 `loading=True`
- hit 快路径不会污染 `loading` 状态

### 3) 保持 emit 在锁外(不引入新的死锁风险)

修复仅调整 `entry.loading` 的设置时机,不改变:

- `pending_emits` 的采集仍在锁内
- `instrumentation.emit(...)` 仍在锁外

这保持了现有 reentry/死锁护栏与测试口径不变。

## Risks / Trade-offs

- `entry.loading` 成为跨锁域字段(可能在未持有 `entry.lock` 时写入)。但该字段仅用作 eviction gate,且 eviction 读取发生在持有 `self._lock` 的临界区内,语义明确且可控。
- 若实现遗漏“hit 路径清理 loading”,会导致条目长期不可逐出 → 必须用单测覆盖。

## Migration Plan

- 无需迁移: 仅修复并发竞态,对外配置与 API 不变。

## Open Questions

- 无。本次 fix-0 聚焦关闭竞态窗口;关于 load 异常后的 entry 处理策略(删除/错误缓存/重试退避)另开 change 讨论。
