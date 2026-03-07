# instrumentation-hub Specification

## Purpose
TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.
## Requirements
### Requirement: `loader_retry` 事件必须 wants-gated 且 payload 懒构建
系统 MUST 将 `loader_retry` 事件纳入 `InstrumentationHub` 统一分发,并遵循 wants-gated + lazy payload 语义:
- 当 `InstrumentationHub.wants("loader_retry")=false` 时,系统 MUST 不构建 payload、不得创建 `Event` envelope、不得进入锁区.
- 当存在订阅者时,系统 MUST 正常分发该事件给 observers 与 `IExecutionHook.on_event(Event)` 订阅者.

#### Scenario: 无订阅者时不构建 payload
- **GIVEN** 未注册任何订阅 `loader_retry` 的 hooks/observers
- **WHEN** 执行过程中发生一次可重试失败
- **THEN** 系统 MUST 不构建 `loader_retry` payload(等价于 `emit_lazy` 的 factory 不被调用)
