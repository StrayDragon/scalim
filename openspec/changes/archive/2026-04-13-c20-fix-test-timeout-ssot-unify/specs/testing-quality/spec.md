# testing-quality (delta) Specification

## ADDED Requirements

### Requirement: Test timeouts MUST use SSOT constants and helpers

`tests/` 下的测试 MUST 使用 `tests/support/testing_utils.py` 中定义的超时 SSOT（例如 `CI_TIMEOUT_S`、`NEGATIVE_TIMEOUT_S`、`POLL_DEADLINE_S`）及配套 helper（例如 `event_wait`、`barrier_wait`、`join_or_fail`、`future_result`），而不得依赖与 SSOT 不一致的硬编码超时字面量。

- 对 `wait(timeout=...)` 等模式，测试 SHOULD 统一为 `event_wait(...)` / `future_result(...)` 等 helper，除非有明确理由保持原 API。
- 若某场景确需长于默认 SSOT 的等待时间，测试 MUST 使用 `CI_TIMEOUT_S` 的整数倍（例如 `CI_TIMEOUT_S * 3`）并附注释说明原因，而不得使用与 CI 不可调协的裸数字。
- 系统 MAY 提供可选的治理扫描，用于发现 `tests/` 中未使用 SSOT 的 `timeout=` 字面量并 fail-fast。

#### Scenario: workflow cache pool tests use SSOT timeouts

- **WHEN** 维护者审阅 `tests/workflow/test_workflow_cache_pool.py` 等需等待并发/IO 的用例
- **THEN** 超时与等待 MUST 基于 `CI_TIMEOUT_S` 与 `event_wait`（或等价 helper），而不得使用模块级私有超时常量或与 SSOT 不一致的 `wait(timeout=...)` 字面量

#### Scenario: long-running smoke tests scale with CI timeout

- **WHEN** 某 smoke 用例需要长于默认 `CI_TIMEOUT_S` 的端到端等待
- **THEN** 等待时长 MUST 表达为 `CI_TIMEOUT_S` 的倍数（或等价 SSOT 组合）并具备可审阅的注释
- **AND** CI 通过环境变量调整 SSOT 时，该用例的等待 MUST 随之缩放

#### Scenario: optional timeout literal gate catches drift

- **GIVEN** 仓库启用了针对 `tests/` 的 `timeout=` 字面量治理扫描
- **WHEN** 新测试引入未豁免的硬编码 `timeout=` 等待
- **THEN** 治理扫描 MUST 失败并指出位置
