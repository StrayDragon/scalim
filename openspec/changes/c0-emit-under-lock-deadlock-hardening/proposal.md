## Why

当前有若干执行路径在持有内部互斥锁时调用 `instrumentation.emit(...)`，而 `emit` 会触发用户可注入的 hooks/observers 回调（本质是外部回调）。这在运行时存在“可重入导致自死锁 / 锁顺序反转导致交叉死锁”的高风险：

- 同一线程：A 持有 `Lock` → 调用 `emit` → hook 回调再次尝试获取 A 的 `Lock`（非 reentrant）→ 立即自死锁
- 多线程：A 持有资源锁 → `emit` 获取 hook/observer 内部锁；另一线程先持有 hook/observer 内部锁 → 回调触发资源路径尝试获取资源锁 → 锁顺序反转，形成交叉死锁

这类死锁通常表现为“偶发卡死”，会拖垮整套 workflow/demand 执行与 CI（尤其当 hooks/observers 被用于诊断、指标、审计等场景时回调更复杂）。

当前至少两处明确存在该风险：

- `src/scalim/execution/workflow_cache_pool.py`：`WorkflowCachePool.get_or_load()` 在 `self._lock` 内触发 `EVENT_DIAGNOSTIC_WARNING`（signature conflict 的 warn/separate 路径）
- `src/scalim/dsl/by_yaml/runtime/workflow_resources.py`：`WorkflowResources.apply_sheetbook_sheet()` 在 `self._lock` 内触发 `EVENT_WORKFLOW_RESOURCE_WRITE`（on_conflict=skip 路径）

### 最小复现（概念性）

下面展示“单线程自死锁”的典型结构（示意）：

1. 注册一个 hook：在 `on_diagnostic_warning(...)` / `on_event(...)` 回调内调用会再次进入 cache_pool/resources 的 API
2. 触发会在持锁期间 `emit` 的分支（例如 cache_pool signature conflict + warn；或 sheetbook_sheet 冲突 + skip）
3. 由于 cache_pool/resources 使用的是 `threading.Lock`（非 `RLock`），回调重入会直接卡死

## What Changes

- 将所有 `emit(...)`（以及任何“外部回调/用户回调”）从内部互斥锁临界区中移出
  - 在锁内只做：状态检查/状态更新/必要的 payload 字段采集
  - 解锁后再做：`instrumentation.emit(...)` / 日志 / 回调
- 对需要“锁内早退”的路径（例如 on_conflict=skip）：
  - 在锁内决定 action + 记录必要上下文
  - 解锁后 emit，再返回
- 增加回归测试（防止未来回归把 emit 再次搬回锁内）
  - 构造一个会在 hook 回调里重入 cache_pool/resources 的 hook
  - 触发对应分支并断言不会卡死（使用 `join(timeout=...)` + fail-fast）

## Capabilities

### New Capabilities
- `no-external-callback-under-lock`: 定义执行层的通用并发护栏：任何可能触发用户回调/observer/hook 的操作 MUST 不得在内部互斥锁临界区内执行（包含 emit/log-callback 等）。

### Modified Capabilities
- `workflow-cache-pool`: 补充并发与可观测性要求：cache_pool 的事件发射 MUST 不得在 pool 内部锁临界区内执行。
- `workflow-sheetbook-resources`: 补充并发与可观测性要求：资源写入事件发射 MUST 不得在资源内部锁临界区内执行。

## Impact

- 受影响代码路径：
  - `src/scalim/execution/workflow_cache_pool.py`（signature conflict + 诊断事件）
  - `src/scalim/dsl/by_yaml/runtime/workflow_resources.py`（sheetbook 写入冲突路径）
- 行为语义：
  - 事件的 “何时发射” 可能从“锁内”移动到“锁外、紧随状态更新之后”，但对外可见的事件内容与顺序应保持等价（具体顺序约束在 design/spec 中明确）
- 可靠性收益：
  - 显著降低偶发卡死/死锁风险，提升 workflow 执行与 CI 稳定性；同时为后续引入更复杂的 hooks/observers 提供安全基础
