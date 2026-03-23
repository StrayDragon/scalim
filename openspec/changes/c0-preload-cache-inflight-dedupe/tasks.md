## 1. Inflight 状态与序列化边界

- [ ] 1.1 在 `src/scalim/execution/preload_cache.py` 引入 `_InFlight`（`Event` + `owner_ident` + `value/error`），并新增 `_inflight: Dict[str, _InFlight]`
- [ ] 1.2 更新 `__setstate__` 重置 `_inflight`（与 `_locks/_global_lock` 一样不参与 pickle），确保 `adaptive` 的 `process` 后端 smoke 不回归

## 2. `get_or_load` 并发语义重构（锁外执行）

- [ ] 2.1 重构 `PreloadCache.get_or_load()`：锁内仅做 inflight 建档/提交；锁外执行 `load_fn()` 与 `Event.wait()`
- [ ] 2.2 加入“同线程重入同 key”fail-fast 护栏：检测到 `owner_ident == threading.get_ident()` 时抛出明确异常，避免自死锁
- [ ] 2.3 明确异常传播策略：实现 best-effort “异常克隆后再 raise”（失败则回退到直接 raise），保证等待方异常类型/信息一致

## 3. 并发回归测试（可验证、可防卡死）

- [ ] 3.1 新增测试：两个线程并发同 key，`load_fn` 只执行一次，两个线程返回相同 mapping（若现有 `tests/test_preload_cache.py` 覆盖则保留并确保稳定）
- [ ] 3.2 新增测试：`load_fn` 抛异常时，所有等待方收到一致异常，且 `_data` 不写入半成品；再次调用会触发重试（inflight 已清理）
- [ ] 3.3 新增测试：`load_fn` 直接/间接重入同 key 时 fail-fast（使用 `join(timeout=...)` 作为护栏，确保不会卡死拖垮 CI）

## 4. 验收口径（SSOT）

- [ ] 4.1 运行 `just qa`（包含 py36 smoke / tests / openspec-check / drift gates），确保全绿且无工作区漂移

