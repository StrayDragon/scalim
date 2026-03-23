## 1. WorkflowCachePool：锁外发射事件

- [ ] 1.1 在 `src/scalim/execution/workflow_cache_pool.py` 中重构 `WorkflowCachePool.get_or_load()`：锁内只更新状态并收集事件所需字段；解锁后依次 `instrumentation.emit(...)`（保持 warning 在 acquire 之前）。
- [ ] 1.2 重构 release/evict 相关路径（例如 `on_workflow_node_done()` / `_emit_release_events()` / `_evict_entry()` / `close()` / 预算淘汰路径）：禁止在持有 `self._lock` 时调用 `instrumentation.emit(...)`；payload/meta 保持与现有一致（包含 `remaining_consumers` 的既有语义与计算时点）。
- [ ] 1.3 增加回归测试：构造 `instrumentation.emit` 内同步重入 `WorkflowCachePool.get_or_load()` 的回调；将触发路径放入 `daemon` 线程并 `join(timeout=...)`，断言不会卡死。

## 2. WorkflowResourceManager：锁外发射 warning/write

- [ ] 2.1 在 `src/scalim/dsl/by_yaml/runtime/workflow_resources.py` 中梳理并改造所有 `with self._lock:` 临界区：禁止锁内直接 `instrumentation.emit(...)`，也禁止锁内调用 `_emit_resource_write(...)`（包括 `skip`/`warn` 分支与 early-return）。
- [ ] 2.2 将 `plan.last_workflow_node_id` 的更新移动到锁内并置于事件发射前，确保回调收到事件时能观察到已提交的状态。
- [ ] 2.3 保持事件相对顺序：同一次调用中若既有 mismatch warning 又有 resource_write，则 warning 先于 write 发射（锁内准备 payload，锁外发射）。
- [ ] 2.4 增加回归测试：构造 `instrumentation.emit` 回调重入 `WorkflowResourceManager` 的 `apply_*` API；使用 `daemon` 线程 + `join(timeout=...)` fail-fast，验证不会卡死。

## 3. 验收与护栏

- [ ] 3.1 代码层护栏：在实现后用 `rg \"emit\\(\"`（或等价方式）确认 `workflow_cache_pool.py` 与 `workflow_resources.py` 中不存在“锁内 emit/锁内 _emit_resource_write”路径。
- [ ] 3.2 运行测试：至少执行 `pytest -k \"workflow_cache_pool or workflow_resources\"`；推荐在提交前跑 `just qa`。
- [ ] 3.3 OpenSpec 校验：运行 `just openspec-check`，确保该 change 的工件与规格一致。
