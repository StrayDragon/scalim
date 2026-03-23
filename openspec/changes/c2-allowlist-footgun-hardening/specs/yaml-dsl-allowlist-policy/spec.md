# yaml-dsl-allowlist-policy Specification

## Purpose
为 by_yaml 的 Python 引用 resolver 定义“安全默认 + 显式 opt-in”的 allowlist/trusted-mode/denylist-only 语义，消除 `"*"` 与不安全开关导致的误配置脚枪，并提供强诊断与迁移指引。

## ADDED Requirements

### Requirement: wildcard MUST be rejected by default
当调用方为 allowlist 提供通配符 `"*"`（例如 `allowed_modules={"*"}` 或 `allowed_functions={"*"}`）且未显式启用 trusted-mode 时，系统 MUST fail-fast，并给出可操作的错误信息（例如提示开启 trusted-mode 或改为显式 allowlist）。

#### Scenario: wildcard in allowed_modules is rejected by default
- **WHEN** 调用方未启用 trusted-mode
- **AND** 运行入口收到 `allowed_modules={"*"}`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 明确指出 `"*"` 默认被禁止并提供迁移建议（trusted-mode / 显式 allowlist）

### Requirement: trusted-mode MUST be explicit and MUST warn loudly
系统 MUST 提供显式 trusted-mode（或等价显式开关），仅当调用方显式启用时才允许放宽 allowlist 约束。

当启用 trusted-mode 时，系统 MUST 发出强风险告警（至少 warning 级日志；可选事件/诊断输出），且告警内容 MUST 可让用户明确理解当前处于“不安全/全放开或放宽约束”的运行模式。

#### Scenario: trusted-mode enables wildcard with warnings
- **GIVEN** 调用方显式启用 trusted-mode
- **WHEN** 运行入口收到 `allowed_modules={"*"}`（或等价全放开配置）
- **THEN** 系统 MUST 允许继续执行
- **AND** 系统 MUST 发出明确的风险告警（warning）

### Requirement: allowed_functions wildcard MUST NOT be mixed with allowed_modules
系统 MUST 拒绝 `allowed_functions={"*"}` 与 `allowed_modules` 混用的配置，并给出可操作的替代方案：
- 若希望“对模块做约束”，则应移除 `allowed_functions={"*"}` 并仅使用 `allowed_modules`
- 若希望“全放开”，则应使用统一的 trusted-mode（而不是混合配置）

#### Scenario: allowed_functions wildcard mixed with allowed_modules is rejected
- **WHEN** 运行入口同时收到 `allowed_modules={"myapp.loaders"}` 与 `allowed_functions={"*"}`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指出该组合会旁路模块约束，并提示使用 trusted-mode 或仅保留 `allowed_modules`

### Requirement: denylist-only resolver mode MUST require double confirmation
系统 MAY 提供“denylist-only（不安全）”的 resolver 模式以支持测试/演示/可信输入场景；但当调用方尝试启用该模式时，系统 MUST 要求额外的显式确认信号（例如环境变量或二次确认参数）。

当确认信号缺失时，系统 MUST fail-fast，并提示如何正确启用（含风险说明）。

#### Scenario: denylist-only mode requires extra confirmation
- **WHEN** 调用方请求启用 denylist-only（不安全）resolver 模式
- **AND** 额外确认信号缺失（例如未设置要求的环境变量）
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 说明该模式不安全且需要额外确认
