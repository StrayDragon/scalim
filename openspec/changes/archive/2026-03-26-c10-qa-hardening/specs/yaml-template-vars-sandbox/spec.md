## ADDED Requirements

### Requirement: unsafe entrypoints MUST be auditable and MUST warn about legacy sandbox deprecation
当调用方通过显式 `unsafe` 语义入口启用不安全能力时，系统 MUST 产生可观测的 warning 级审计输出。

当 `template_sandbox="legacy"` 被使用时，系统 SHOULD 额外输出弃用警告，提示迁移到 `safe`。

#### Scenario: unsafe entrypoint emits audit warning
- **WHEN** 调用方调用 `unsafe_run/unsafe_compile`
- **THEN** 系统 MUST 产生 warning 级告警/审计输出

#### Scenario: legacy sandbox emits deprecation warning
- **WHEN** 调用方通过 `unsafe` 入口启用 `template_sandbox="legacy"`
- **THEN** 系统 SHOULD 产生弃用警告（deprecation）
