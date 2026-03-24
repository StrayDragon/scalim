## 1. 诊断配置与等待实现

- [ ] 1.1 定义 `PreloadCache` 的 wait diagnostics 配置结构（默认 disabled；包含 `warn_after_s` 等阈值参数）
- [ ] 1.2 在 `PreloadCache._get_or_load_waiter()` 中实现“仅在开启诊断时”的循环等待（基于 `time.monotonic()` 计算 `wait_s`）
- [ ] 1.3 保证默认关闭路径仍是单次 `inflight.done.wait()`（不新增语义变化与额外开销）

## 2. 稳定诊断信号（日志）

- [ ] 2.1 使用 `src/scalim/_internal/loggingx.py` 输出 `[scalim] preload-cache:` 前缀的 warning
- [ ] 2.2 warning 字段至少包含 `source_id` 与 `wait_s`（可追加 `owner_thread_ident` 等稳定字段）

## 3. 测试与验收

- [ ] 3.1 在 `tests/test_preload_cache.py` 增加用例：默认关闭时不产生 warning
- [ ] 3.2 增加用例：显式开启诊断 + 低阈值时会产生包含稳定字段的 warning（`caplog` 断言），并用 `join(timeout=...)` 防止挂死
- [ ] 3.3 运行 `just qa` 与 `just openspec-check`（本变更无 `.gen.*` 生成物/注入区块需要刷新）

## 4. 后置提案（仅 proposal.md）

- [ ] 4.1 若需要“极端调试模式”（等待超过更大阈值时抛异常/timeout），创建后置 change `c700-*`（仅 `proposal.md`）讨论该行为变更的验收口径；不得在本变更默认语义中引入 timeout/抛错
