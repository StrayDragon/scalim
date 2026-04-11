## 1. 用事件驱动替代轮询等待（方案 A）

- [ ] 1.1 在 `tests/workflow/test_workflow_resources_coverage.py` 的 instrumentation stub（例如 `_Instrumentation.emit`）中新增同步信号：当 `event_type == EVENT_DIAGNOSTIC_WARNING` 时 `warning_event.set()`
- [ ] 1.2 将轮询 `instrumentation.events` + `sleep(0.01)` 的测试改为 `warning_event.wait(timeout=CI_TIMEOUT_S)` 驱动，并在超时失败时输出诊断（已收集事件数/最近事件）

## 2. 避免微小阈值断言（方案 B）

- [ ] 2.1 将 `warn_after_s=0.3` 等微小阈值提升为更宽裕且可配置的值（至少秒级；必要时使用 `CI_TIMEOUT_S`）
- [ ] 2.2 用 `Event/Barrier` 协调同步点：确保被测 wait loop 已进入等待状态后再触发 `done.set()`，移除 `sleep(0.05)` 这类时序推进方式

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/workflow-runtime-quality-and-test-stability/spec.md` 增加 “测试 MUST 避免 sleep/polling，使用显式事件信号” 的要求
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 重复运行相关测试子集（例如 `pytest -q tests/workflow/test_workflow_resources_coverage.py -k wait_diagnostics` 20 次）并跑 `just quick-qa-only-py` 作为最终验收

