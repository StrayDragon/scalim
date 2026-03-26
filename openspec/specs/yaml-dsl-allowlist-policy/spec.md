# yaml-dsl-allowlist-policy Specification

## Purpose
TBD - created by archiving change c2-allowlist-footgun-hardening. Update Purpose after archive.
## Requirements
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

### Requirement: trusted_allow_all_modules MUST be gated by an explicit env var
当调用方显式启用 `resolver_trusted_mode=trusted_allow_all_modules` 时,系统 MUST 要求环境变量 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`,否则 MUST fail-fast.

该门控用于防止误在生产环境中启用“等效代码执行权限”的模式.

#### Scenario: trusted_allow_all_modules fails without env gate
- **WHEN** 调用方启用 `resolver_trusted_mode=trusted_allow_all_modules`
- **AND** 未设置 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 明确指出需要设置环境变量才能启用

#### Scenario: trusted_allow_all_modules allowed with env gate
- **WHEN** 调用方启用 `resolver_trusted_mode=trusted_allow_all_modules`
- **AND** 设置 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`
- **THEN** 系统 MAY 继续执行
- **AND** 系统 MUST 发出明确的风险告警(warning)

### Requirement: allowed_functions wildcard MUST be rejected
系统 MUST 拒绝 `allowed_functions={"*"}`（无论是否同时提供 `allowed_modules` 或是否处于 trusted-mode），并给出可操作的替代方案：
- 若希望“对模块做约束”，则应移除 `allowed_functions={"*"}` 并仅使用 `allowed_modules`
- 若希望“全放开模块”，则应使用 trusted-mode（而不是依赖 `allowed_functions={"*"}`）

#### Scenario: allowed_functions wildcard is rejected
- **WHEN** 运行入口收到 `allowed_functions={"*"}`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指出该配置无法表达“仍受模块约束”，并提示使用仅 `allowed_modules` 或 trusted-mode

### Requirement: denylist-only escape hatches MUST NOT be implicit
系统 MUST NOT 提供“缺少 allowlist 但继续执行”的隐式逃逸口子（例如通过一个不易理解的 bool 参数绕过 allowlist 要求）。

当 allowlist 缺失时，系统 MUST fail-fast，并提供可复制的修复示例（例如如何配置 `allowed_modules`）。

系统 MAY 提供 denylist-only（不安全）模式以支持内部测试/演示，但必须满足：

- MUST 通过显式的 unsafe entrypoint 或显式参数启用（命名 MUST 包含 `unsafe` 或等价强标识）
- MUST NOT 通过环境变量隐式改变框架处理行为与能力边界
- MUST 与 allowlist/trusted-mode 互斥（混用 MUST fail-fast）

#### Scenario: missing allowlist fails fast
- **WHEN** 调用方未提供 `allowed_modules` 且未提供 `allowed_functions`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提供可复制的 allowlist 配置示例
