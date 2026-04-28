## MODIFIED Requirements

### Requirement: legacy behavior MUST require explicit non-public opt-in

系统 MUST NOT 在任何入口继续支持 legacy/信任模式模板沙箱。

系统 MUST 将 `template_sandbox` 的允许值集合收敛为 `safe`:
- 公共入口收到 `template_sandbox="legacy"`(或等价 legacy opt-in)时 MUST fail-fast,并给出迁移提示
- 非公共/unsafe 入口同样 MUST fail-fast(legacy 已彻底移除,不再提供“逃逸口”)。

并且:
- `_`/`__dunder__` 属性访问 MUST 仍然被禁止(不提供放宽开关)
- method call 语法(例如 `x.y()`) MUST 始终被禁止

#### Scenario: public run API rejects legacy sandbox
- **WHEN** 调用方通过官方公开入口启用 `template_sandbox="legacy"`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 同时满足:
  - 指出系统仅支持 safe sandbox(legacy 已移除)
  - 给出明确迁移动作(例如"移除 `template_sandbox` 参数或显式改为 safe 模式")

#### Scenario: safe sandbox remains the only public template mode
- **WHEN** 调用方通过官方公开入口提供 `template_vars`
- **THEN** 系统 MUST 继续在 YAML parse 前执行 safe sandbox 预编译
- **AND** 不得再通过任何公共入口放宽为 legacy 模式

#### Scenario: unsafe entrypoint rejects legacy sandbox
- **WHEN** 调用方通过 `unsafe` 语义入口传入 `template_sandbox="legacy"`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指出 legacy 已移除并提示迁移到 safe

## REMOVED Requirements

### Requirement: unsafe entrypoints MUST be auditable and MUST warn about legacy sandbox deprecation

**Reason**: legacy sandbox 已彻底移除,不再存在“legacy 使用时的弃用警告”语义。

**Migration**: unsafe 入口仍需保留审计 warning,但不再区分 legacy/safe。参见本 change 新增的 "unsafe entrypoints MUST be auditable" 要求。

## ADDED Requirements

### Requirement: unsafe entrypoints MUST be auditable

当调用方通过显式 `unsafe` 语义入口调用不安全能力时,系统 MUST 产生可观测的 warning 级审计输出。

说明:
- 该审计输出的目标是让“unsafe 能力的使用”在日志/可观测链路中可追踪。
- legacy sandbox 不再存在,unsafe 入口不再承担 legacy 兼容与弃用提示。

#### Scenario: unsafe entrypoint emits audit warning
- **WHEN** 调用方调用 `unsafe_run/unsafe_compile`(或等价 unsafe 入口)
- **THEN** 系统 MUST 产生 warning 级告警/审计输出
