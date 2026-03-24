# workflow-runtime-quality-and-test-stability Specification

## Purpose
TBD - created by archiving change c1-workflow-runtime-quality-and-test-stability. Update Purpose after archive.
## Requirements
### Requirement: workflow entrypoints MUST support dependency injection without module-global mutation
系统 MUST 支持对 workflow 执行关键依赖（例如 `run_ir`）进行显式依赖注入（用于单测与内部替换）,且该机制 MUST 不通过写模块全局变量实现,以保证并发执行可预期。

#### Scenario: injected executor does not cross-contaminate concurrent runs
- **WHEN** 两个并发的 workflow 执行分别使用不同的注入执行器
- **THEN** 每次执行 MUST 只调用其自身注入的执行器,不得互相污染

### Requirement: JSON-like validation MUST be centralized as SSOT
系统 MUST 将 “JSON-like 校验” 收敛为单一 SSOT 实现,并在 workflow ctx 与缓存签名等路径复用,以避免规则漂移导致的不可预期行为或错误信息不一致。

#### Scenario: non-finite float is rejected consistently
- **WHEN** 任一路径对 JSON-like 值校验遇到非有限 float（`NaN/Inf`）
- **THEN** 系统 MUST fail-fast 且错误信息 MUST 可用于定位输入路径

### Requirement: concurrency tests MUST be deterministic and avoid wall-clock flakiness
系统的并发/诊断类测试 MUST 避免依赖极小的真实时间阈值与 `time.sleep` 驱动,并提供足够的 timeout 与明确的完成信号,以降低 CI 抖动导致的 flaky 或误报死锁。

#### Scenario: deadlock detection tests do not rely on 1s join timeout
- **WHEN** 某个测试用例用于验证“无死锁/可重入”
- **THEN** 该测试 MUST 以明确完成信号作为断言依据,而不是仅依赖 `join(timeout=1.0)` 的是否超时

