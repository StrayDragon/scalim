## Context

`WorkflowCachePool` 与 `WorkflowResourceManager` 都使用 `threading.Lock` 保护内部状态（`self._lock`）。当前代码存在在持有该锁的临界区内调用 `instrumentation.emit(...)` 的路径。

由于 `emit(...)` 可能同步触发用户可注入的 hooks/observers（外部回调），这会引入高风险的死锁形态：

- **同线程自死锁（可重入）**：A 持有 `self._lock` → 调用 `emit` → 回调重入 A 的 API 再尝试获取 `self._lock`（非 `RLock`）→ 卡死
- **多线程交叉死锁（锁顺序反转）**：A 持有资源锁 → `emit` 内部获取 hooks/observers 相关锁；另一线程先持有 hooks/observers 锁 → 回调进入资源路径尝试获取资源锁 → 交叉死锁

该问题通常表现为“偶发卡死”，对 workflow 执行与 CI 都是高优先级风险。

本变更聚焦在两处已确认的组件：

- `src/scalim/execution/workflow_cache_pool.py`：`WorkflowCachePool` 在 `self._lock` 内发射多种事件（diagnostic/acquire/release/evict）。
- `src/scalim/dsl/by_yaml/runtime/workflow_resources.py`：`WorkflowResourceManager` 在 `self._lock` 内发射 diagnostic warning，且在若干 early-return 分支中锁内调用 `_emit_resource_write(...)`。

约束：

- 运行时代码需保持 Python 3.6 兼容。
- 该变更不触及生成文档/注入区块；不需要 `just gen-docs`。
- 变更应尽量保持事件载荷（payload/meta）与“同一次调用内”的事件相对顺序不变。

## Goals / Non-Goals

**Goals:**

- 在上述组件中建立并落实护栏：任何可能触发外部回调的 `instrumentation.emit(...)` 不得在内部互斥锁临界区内执行。
- 将临界区收敛为“仅状态读写 + 必要字段采集/快照”，在解锁后再发射事件。
- 增加回归测试：构造“emit 回调重入同一组件 API”的场景，确保不会卡死（fail-fast）。
- 覆盖范围明确：仅聚焦 `WorkflowCachePool` 与 `WorkflowResourceManager`，但覆盖其内部所有事件发射路径（不只局部 if 分支）。

**Non-Goals:**

- 不将 `Lock` 替换为 `RLock` 作为主要方案（这只能缓解自死锁，且仍可能引入锁顺序反转/隐藏问题）。
- 不改变事件类型定义与对外 API（除了事件发射从锁内移动到锁外的时机变化）。
- 不在本次变更中全仓库扫清所有“锁内回调”模式（可作为后续工作）。
- 不改变事件字段语义（尤其是 `WorkflowCacheReleaseEvent.remaining_consumers` 的计算口径保持现状），避免观测回归。

## Decisions

### 1) 采用“两段式 emit”模式（Collect → Emit）

统一策略：

1. **锁内**：完成状态判断/更新，并将事件所需字段复制到局部变量（构造 event payload 所需的原始值或已冻结的 payload）。
2. **解锁后**：按既定顺序调用 `instrumentation.emit(...)`（以及其它外部回调/日志回调）。

这保证：

- 不在持锁期间触发外部回调，从根源规避死锁。
- 事件发射发生在状态更新之后（满足规范的并发一致性要求）。

### 2) 在 `WorkflowCachePool` 中“收集事件列表”并在锁外统一发射

在 `WorkflowCachePool.get_or_load()` 里，可能同时触发：

- `EVENT_DIAGNOSTIC_WARNING`（signature conflict + warn/separate）
- `EVENT_WORKFLOW_CACHE_ACQUIRE`

实现上在锁内收集一个按序的 `events_to_emit = [(event_type, payload, meta), ...]`，解锁后依次发射，保证“同一次调用内”的事件相对顺序保持（warning 在 acquire 之前）。

对于 release/evict 相关路径：

- 将当前锁内直接 `emit` 的 helper（例如 release/evict）调整为“只产生事件载荷”，由外层在解锁后统一发射。
- 确保事件 payload 使用基础类型/冻结对象（例如 `tuple(...)`、`str(...)`），避免解锁后被共享可变对象修改。

### 3) 在 `WorkflowResourceManager` 中避免任何锁内 `_emit_resource_write(...)` / diagnostic emit

在 `WorkflowResourceManager` 中，主要风险点来自：

- mismatch `warn` 分支：锁内发射 `EVENT_DIAGNOSTIC_WARNING`
- `skip` 分支：锁内调用 `_emit_resource_write(...)`（其内部会 `instrumentation.emit`）

策略：

- 锁内只决定 `action`、更新 `plan/sheet_plan` 等状态，并准备好 `resource_write` 与 `diagnostic_warning` 的参数（或 payload）。
- 解锁后按顺序发射：若同一次调用既有 warning 又有 write，则先 warning 后 write，保持既有语义直觉。

### 4) 回归测试采用 “daemon thread + join(timeout)” fail-fast 方式

为了避免测试本身把 CI 卡死：

- 将“可能卡死的调用”放到 `daemon=True` 的线程中执行。
- 主线程 `join(timeout=...)`，超时则立即 `pytest.fail(...)`。

测试构造思路：

- 伪造一个 `instrumentation.emit(...)`：在 `emit` 内同步调用一个会重入组件 API 的回调（只执行一次，避免无限递归）。
- 如果 `emit` 仍在锁内执行，会在重入时自死锁；如果按本设计移到锁外，则不会卡死。

### 5) 明确并发边界：保证“不死锁 + 快照一致”，不保证“回调可安全做任意写操作”

本变更提供的并发契约：

- **MUST**：`emit(...)`/外部回调不在内部互斥锁临界区内执行（避免死锁）。
- **MUST**：事件 payload/meta 在锁内完成快照采集，解锁后发射，避免发射时读取到漂移的可变状态。
- **MUST**：与事件相关的核心状态更新先于事件发射完成（例如资源写入计划、last node id 等）。
- **NOT guaranteed**：回调重入后对同一组件执行“写操作 API”的时序与可见性（可能与原调用交错）。回调应尽量视事件为通知，不应依赖强一致的“回调内读取到完全静止的全局状态”。

回归测试的目标也限定为：验证“重入会尝试获取同一把锁”时不会卡死，而不是验证回调重入的业务语义。

### 6) `WorkflowResourceManager.plan.last_workflow_node_id` 更新顺序

为匹配“事件在状态更新之后发射”的要求，本变更将把 `plan.last_workflow_node_id` 的更新移动到锁内、事件发射之前完成：

- 锁内：更新 `plan/sheet_plan` 等状态 + 设置 `plan.last_workflow_node_id`
- 锁外：发射 `EVENT_WORKFLOW_RESOURCE_WRITE`（以及可能的 diagnostic warning）

这让回调在接收事件时能观察到最新的 `last_workflow_node_id`，同时仍满足“不在锁内回调”的护栏。

### 7) `WorkflowCacheReleaseEvent.remaining_consumers` 语义保持现状

当前实现的 `remaining_consumers` 是在 `on_workflow_node_done()` 的 refcount 递减（discard `node_id`）之前计算的。该口径可能不直觉，但本变更将其视为既有外部可观测语义的一部分：

- **本变更不调整其计算时点**，仅将事件发射移到锁外并对 payload 做快照。
- 若后续希望改为“释放后的 remaining”，建议单独开 change，避免与并发安全修复耦合。

## Risks / Trade-offs

- **事件发射与并发交错**：解锁后发射事件期间，其他线程可能推进状态；但本设计保证事件发射发生在“对应状态更新之后”，且 payload 已在锁内完成快照，避免读到不一致的可变状态。
  - 缓解：尽量让 payload 仅包含不可变/复制后的值；不承诺跨线程的全局事件顺序。
- **引入局部复制成本**：为保证解锁后 payload 稳定，可能需要复制 list/dict。
  - 缓解：仅复制事件需要的字段；热路径可在后续结合 `instrumentation.wants(...)` 做更细的门控（不属于本变更必需）。
- **回归风险**：未来维护者可能再次在锁内调用 `emit`。
  - 缓解：新增回归测试 + 在实现中统一封装“收集后发射”模式，减少误用面。

## Migration Plan

- 实施修改：
  - 只修改运行时代码与测试文件；不涉及生成文件/注入区块。
  - 验收以 `pytest`（相关子集）与 `just qa` 为准。
- 回滚策略：
  - 直接 revert 该变更提交即可恢复原行为（注意 revert 会重新引入死锁风险）。

## Future Work (Out of scope)

- 可选：对全仓库做一次“锁内外部回调”扫描，并建立更强的护栏（例如更系统的并发回归测试或 lint 规则）。
- 可选：单独澄清/调整 `WorkflowCacheReleaseEvent.remaining_consumers` 的语义与计算时点（若需要更直觉的“释放后剩余”定义）。
