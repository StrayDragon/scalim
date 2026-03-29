## ADDED Requirements

### Requirement: lock-safe emit MUST also be thread-safe for observers by default

系统 MUST 同时满足两条约束：
- 回调必须在锁外（避免死锁）
- 锁外回调在并发下必须默认安全（避免并发调用 observer 导致竞态）

系统 MUST 通过 capture+replay 或等价的序列化策略实现上述双约束.

#### Scenario: lock-safe emit does not introduce observer races
- **GIVEN** workflow 并发执行且 emit 在锁外
- **WHEN** 同一个 observer 可能被多个线程触发
- **THEN** 系统 MUST 通过序列化/回放避免并发回调

