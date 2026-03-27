## MODIFIED Requirements

### Requirement: 执行层扩展点必须显式注入
系统 MUST 提供显式的 overrides/config 对象用于覆盖 execution pipeline 的可变实现细节(例如批次切分策略与 `adaptive` 调度策略/并发池配置/执行器类型),并禁止通过 `sys.modules` 探测或模块级 `getattr` “魔法注入”实现覆盖.
默认情况下,未提供 overrides 时系统行为 MUST 与现有默认实现一致.

#### Scenario: 覆盖批次切分策略
- **WHEN** 用户提供自定义 `chunk_iterable` overrides
- **THEN** Pipeline 必须使用该 chunker 进行批次切分

#### Scenario: 注入 adaptive tuning/policy
- **WHEN** 用户通过 overrides 注入 `AdaptiveTuning` 或 `AdaptivePolicy`
- **THEN** `parallel_mode=adaptive` 的调度 MUST 使用该 tuning/policy 决定并发行为

#### Scenario: 覆盖 adaptive 执行器类型
- **WHEN** 用户通过 overrides 注入自定义的 `adaptive` thread backend executor(thread 的 factory 或等价扩展点)
- **THEN** 调度器 MUST 使用该 executor 创建并发 worker
- **AND** 若用户配置/策略选择到 process/async backend,系统 MUST 失败并说明当前仅支持 thread

