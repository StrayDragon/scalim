## 1. 测试侧同步超时 SSOT（CI_TIMEOUT_S/NEGATIVE_TIMEOUT_S）

- [ ] 1.1 在 `tests/support/` 增加/扩展线程同步 helper：对 `Barrier.wait` / `Event.wait` / `Future.result` 等等待封装统一入口，正向等待默认使用 `CI_TIMEOUT_S`，负向断言使用 `NEGATIVE_TIMEOUT_S`
- [ ] 1.2 helper 在超时/失败时输出诊断信息（至少线程信息；必要时线程栈），便于定位真实死锁 vs CI 抖动

## 2. 迁移代表性 flaky 点位（移除 1s/2s 硬编码）

- [ ] 2.1 迁移 `tests/execution/test_thread_safety.py` 中 `Barrier.wait(timeout=1.0)` 等硬编码超时到 SSOT/helper
- [ ] 2.2 迁移 `tests/execution/test_adaptive_execution_tuning.py` 的 `Event.wait(timeout=1.0)` 等硬编码超时到 SSOT/helper
- [ ] 2.3 迁移 `tests/yaml_dsl/test_yaml_dsl_lsp_cache.py` 中 `timeout=2` / `fut.result(timeout=2)` 等到 SSOT/helper

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/workflow-runtime-quality-and-test-stability/spec.md` 补充 “并发测试 timeout 口径集中 + 超时诊断” 要求
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 重复运行相关测试子集（至少 10 次）验证 flaky 为 0，并跑 `just quick-qa-only-py` 作为最终验收

