# workflow-runtime-quality-and-test-stability (delta) Specification

## MODIFIED Requirements

### Requirement: concurrency tests MUST be deterministic and avoid wall-clock flakiness
系统的并发/诊断类测试 MUST 避免依赖极小的真实时间阈值与 `time.sleep` 驱动,并提供足够的 timeout 与明确的完成信号,以降低 CI 抖动导致的 flaky 或误报死锁。

为保证“可重复 + 可诊断”，系统 MUST 同时满足：

- 正向等待（期望完成）的超时阈值 MUST 通过测试 SSOT 常量统一管理（例如 `CI_TIMEOUT_S`），且 MUST 可通过环境变量调整
- 负向断言（期望不发生）的超时阈值 MUST 使用单独常量（例如 `NEGATIVE_TIMEOUT_S`），不得使用硬编码的 `1.0/2` 等阈值作为长期断言依据
- 当等待发生超时/卡死时，测试 SHOULD 输出足够诊断信息（至少包含线程信息；必要时包含线程栈），以降低排障成本

#### Scenario: deadlock detection tests do not rely on 1s join timeout
- **WHEN** 某个测试用例用于验证“无死锁/可重入”
- **THEN** 该测试 MUST 以明确完成信号作为断言依据,而不是仅依赖 `join(timeout=1.0)` 的是否超时

#### Scenario: positive waits use configurable CI timeout constant
- **WHEN** 测试用例需要等待 barrier/event/future 完成
- **THEN** 该等待的 timeout MUST 使用集中配置的 `CI_TIMEOUT_S`（或等价 SSOT 常量）
- **AND** 在 CI 变慢时，调用方 MUST 能通过环境变量调整该阈值而无需改测试源码

#### Scenario: timeout failures include diagnostics
- **WHEN** 某个并发测试的等待发生超时
- **THEN** 失败信息 SHOULD 包含可用于定位的诊断输出（例如线程名/存活状态/线程栈摘要）

