## ADDED Requirements

### Requirement: compute failures MUST NOT log raw expressions by default
当 compute 表达式求值失败时，系统 MUST 避免在日志/异常信息中输出表达式原文；系统 MUST 使用稳定的表达式哈希（或等价可追踪但不可逆的标识）用于诊断关联。

#### Scenario: error message contains expression hash instead of raw expression
- **WHEN** compute 表达式求值失败
- **THEN** 抛出的错误信息 MUST 使用 `expr_hash`（或等价标识）而不是表达式原文

### Requirement: compute audit callback MUST support redaction
系统 MUST 提供可选的脱敏审计回调实现，用于在启用审计时仅记录表达式标识与字段名（不记录字段值与结果）。

#### Scenario: redacted audit logs only field names
- **WHEN** 使用脱敏审计回调
- **THEN** 审计输出 MUST 不包含字段值与结果的原始内容

### Requirement: compile cache operations MUST be safe under concurrent access
当多个线程共享同一个 `SecureComputeEngine` 实例时，编译缓存（有界 LRU）的访问/更新 MUST 为线程安全（不得产生内部结构损坏或抛出非预期异常）。

#### Scenario: concurrent compile does not crash
- **GIVEN** 多个线程共享同一个 `SecureComputeEngine` 实例
- **WHEN** 多个线程并发调用 `SecureComputeEngine.compile()`
- **THEN** 系统 MUST 不得因缓存并发读写导致非预期异常
