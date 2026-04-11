## 1. 竞态窗口修复(get_or_load loading 意图)

- [ ] 1.1 在 `src/scalim/execution/workflow_cache_pool.py` 的 `WorkflowCachePool.get_or_load()` 中,对 “miss 且将进入 load” 的调用在释放 `self._lock` 前设置 `entry.loading=True`（覆盖 existing entry 且 `value=None` 的重试路径）
- [ ] 1.2 在 `with entry.lock:` 内补齐 hit 快路径清理: 若 `entry.value is not None` 则在返回前确保 `entry.loading=False`,避免出现永久 loading 导致无法 eviction
- [ ] 1.3 保持 `instrumentation.emit(...)` 仍在锁外执行(不引入 reentry 死锁);必要时补充注释/断言或复用现有测试口径

## 2. 回归测试(并发 + over-budget eviction)

- [ ] 2.1 在 `tests/workflow/test_workflow_cache_pool.py` 新增并发回归用例: 先制造 `value=None` 的 entry(通过首次 load 异常),再在“释放全局锁 → 获取 entry.lock”窗口并发触发 `evict_lru` over-budget 路径
- [ ] 2.2 断言: 修复后 eviction MUST 跳过该条目并导致新增条目 fail-fast(无可淘汰),且重试 load 成功后该 entry 仍保留在 pool 中,后续 `get_or_load` 为 hit

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT: 更新 `openspec/specs/workflow-cache-pool/spec.md` 的 “eviction MUST NOT evict in-flight entries” 要求以覆盖 retry miss 窗口
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 跑 `just qa` 作为最终验收(含 tests/lint/漂移检查)
