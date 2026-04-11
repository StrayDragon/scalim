## 1. 移除无锁 hit fast-path（统一 per-source lock 语义）

- [ ] 1.1 在 `src/scalim/execution/preload_cache.py` 的 `PreloadCache.get_or_load()` 移除 guardrail 关闭时对 `_data` 的无锁读取（`source_id in self._data` / `self._data[source_id]`），改为在 `with self._lock_for(source_id):` 临界区内完成 hit 检查与返回
- [ ] 1.2 确认 miss/load 路径仍满足既有护栏：`load_fn()` 不在互斥锁内执行、in-flight 去重语义不变（仅修正 hit 路径线程安全）

## 2. 回归测试（并发读写不抛 KeyError）

- [ ] 2.1 在 `tests/execution/test_preload_cache.py` 新增并发压力用例：多线程并发 `get_or_load(source_id, ...)` 与 owner 写入/删除（`__setitem__` / `__delitem__` 或等价写路径）交错，断言不出现 `KeyError`（或其它 dict 竞态异常）
- [ ] 2.2 测试等待/超时阈值统一使用 `tests/support/testing_utils.py` 的 `CI_TIMEOUT_S`（避免 CI 抖动导致 flaky），必要时在失败信息中输出诊断摘要

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/preload-cache-inflight-dedupe/spec.md`，补充 “cache hit MUST be thread-safe / 不得无锁读写共享 dict” 的要求
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收

