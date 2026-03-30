## ADDED Requirements

### Requirement: public-facing error messages MUST be formatted by a single policy

系统 MUST 提供单点“异常 → 对外消息”格式化策略（默认 redacted,显式 debug 才 full）,并要求所有对外出口统一使用该策略（CLI JSON、viz bundle、workflow report、events error payload 等）.

#### Scenario: the same exception yields consistent external messaging
- **WHEN** 同一异常在不同入口（CLI/Workflow/Viz）被呈现
- **THEN** 对外消息 MUST 遵循同一 redaction 策略且保持一致结构

### Requirement: duplicated error type names MUST be eliminated

系统 MUST 禁止同名异常类型在多个模块重复定义（例如 workflow config error）,以避免语义混淆与捕获不一致.

#### Scenario: a single canonical workflow config error type exists
- **WHEN** 维护者检索 workflow config error 类型定义
- **THEN** 全库 MUST 仅存在一个 canonical 定义,其余入口仅做包装补充上下文

