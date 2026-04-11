# workflow-runtime-quality-and-test-stability Specification

## Purpose
定义 workflow runtime 的质量与测试稳定性要求,包括依赖注入契约、规则 SSOT 复用与并发测试的确定性护栏.
## Requirements
### Requirement: workflow entrypoints MUST support dependency injection without module-global mutation
系统 MUST 支持对 workflow 执行关键依赖（至少包括 `run_ir` 与 demand 编译回调）进行**每次调用级别**的显式依赖注入（用于单测与内部替换）,且该机制 MUST 不通过写模块全局变量实现,以保证并发执行可预期。

建议通过 `IMPL_ROOT.dsl.yaml_dsl.workflow_entrypoints.run_workflow(..., run_ir_fn=..., compile_demand_yaml_fn=...)`（或等价入口）完成注入。

#### Scenario: injected executor does not cross-contaminate concurrent runs
- **WHEN** 两个并发的 workflow 执行分别使用不同的注入执行器/编译回调
- **THEN** 每次执行 MUST 只调用其自身注入的依赖,不得互相污染

### Requirement: JSON-like validation MUST be centralized as SSOT
系统 MUST 将 “JSON-like 校验” 收敛为单一 SSOT 实现,并在 workflow ctx 与缓存签名等路径复用,以避免规则漂移导致的不可预期行为或错误信息不一致。

#### Scenario: non-finite float is rejected consistently
- **WHEN** 任一路径对 JSON-like 值校验遇到非有限 float（`NaN/Inf`）
- **THEN** 系统 MUST fail-fast 且错误信息 MUST 可用于定位输入路径

### Requirement: concurrency tests MUST be deterministic and avoid wall-clock flakiness
系统的并发/诊断类测试 MUST 避免依赖极小的真实时间阈值与 `time.sleep` 驱动,并提供足够的 timeout 与明确的完成信号,以降低 CI 抖动导致的 flaky 或误报死锁。

为保证“可重复 + 可诊断”,系统 MUST 同时满足:

- 正向等待(期望完成)的超时阈值 MUST 通过测试 SSOT 常量统一管理(例如 `CI_TIMEOUT_S`),且 MUST 可通过环境变量调整
- 负向断言(期望不发生)的超时阈值 MUST 使用单独常量(例如 `NEGATIVE_TIMEOUT_S`),不得使用硬编码的 `1.0/2` 等阈值作为长期断言依据
- 当等待发生超时/卡死时,测试 SHOULD 输出足够诊断信息(至少包含线程信息;必要时包含线程栈),以降低排障成本

#### Scenario: deadlock detection tests do not rely on 1s join timeout
- **WHEN** 某个测试用例用于验证“无死锁/可重入”
- **THEN** 该测试 MUST 以明确完成信号作为断言依据,而不是仅依赖 `join(timeout=1.0)` 的是否超时

#### Scenario: positive waits use configurable CI timeout constant
- **WHEN** 测试用例需要等待 barrier/event/future 完成
- **THEN** 该等待的 timeout MUST 使用集中配置的 `CI_TIMEOUT_S`(或等价 SSOT 常量)
- **AND** 在 CI 变慢时,调用方 MUST 能通过环境变量调整该阈值而无需改测试源码

#### Scenario: timeout failures include diagnostics
- **WHEN** 某个并发测试的等待发生超时
- **THEN** 失败信息 SHOULD 包含可用于定位的诊断输出(例如线程名/存活状态/线程栈摘要)
