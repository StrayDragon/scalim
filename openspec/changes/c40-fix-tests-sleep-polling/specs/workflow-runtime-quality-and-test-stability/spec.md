# workflow-runtime-quality-and-test-stability (delta) Specification

## ADDED Requirements

### Requirement: tests MUST avoid `time.sleep`-driven scheduling and polling loops for synchronization

当测试用例需要等待某个并发事件发生（例如 instrumentation 发出 diagnostic warning）时，测试 MUST 使用事件驱动的同步机制（例如 `threading.Event` / `Barrier`）来表达“明确完成信号”，并避免以下 flaky 模式：

- 通过 `time.sleep(0.01/0.05)` 推进时序
- 通过轮询共享列表/队列（例如反复扫描 `instrumentation.events`）+ sleep 的 busy-wait
- 使用微小 wall-clock 阈值（例如 `warn_after_s=0.3`）做“不会发生”断言

#### Scenario: waiting for a warning uses an explicit event signal
- **GIVEN** 测试需要等待 `EVENT_DIAGNOSTIC_WARNING` 出现
- **WHEN** 被测代码触发告警 emit
- **THEN** 测试 MUST 通过显式事件信号（例如 `warning_event.set()` + `warning_event.wait(...)`）完成等待
- **AND** 测试 MUST NOT 通过轮询事件列表 + `sleep(...)` 等待告警出现

#### Scenario: no-warning-before-warn_after avoids micro thresholds
- **GIVEN** 测试需要断言“在 warn_after 之前不会 emit warning”
- **WHEN** 测试构造 wait loop 并在 warn_after 之前完成 `done` 信号
- **THEN** 测试 MUST 通过 `Event/Barrier` 协调同步点而不是依赖 `sleep(...)`
- **AND** `warn_after_s` SHOULD 选择宽裕且可配置的阈值（至少秒级），避免因调度抖动造成误报

