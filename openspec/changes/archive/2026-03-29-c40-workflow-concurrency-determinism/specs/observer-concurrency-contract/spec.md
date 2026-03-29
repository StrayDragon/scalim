## ADDED Requirements

### Requirement: observer callbacks MUST be safe under workflow concurrency by default

当 workflow 以并发模式执行（例如 `max_concurrency>1`）且注册了 observers/hooks/components 时,系统 MUST 默认保证回调调用在并发下安全:

- 系统 MUST NOT 要求 observer 实现方必须是线程安全的才能正确工作
- 系统 MUST 通过序列化回调或 capture+replay（单线程回放）提供默认保障
- 系统 MUST 仍满足 `no-external-callback-under-lock`（不得把回调放回锁内）

#### Scenario: a non-thread-safe observer works correctly under concurrency
- **GIVEN** workflow 并发执行且注册了一个带可变状态的 observer
- **WHEN** workflow 产生多条事件并触发该 observer
- **THEN** observer 的回调 MUST 不被并发调用（同一时刻最多一个回调在执行）
- **AND** 事件序列 MUST 可解释且可复现

### Requirement: a deterministic event ordering policy MUST be defined

系统 MUST 定义并发下事件的稳定排序策略（例如按声明顺序、按时间戳、或按节点/批次拓扑顺序）,并用于 replay/drain 阶段.

#### Scenario: repeating a concurrent run yields the same event order
- **WHEN** 对同一 workflow 配置在并发模式下重复运行多次
- **THEN** 关键编排级事件序列（pipeline start/end、workflow node start/end、resource commit）MUST 保持一致顺序

