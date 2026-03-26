## ADDED Requirements

### Requirement: trusted_allow_all_modules MUST be gated by an explicit env var
当调用方显式启用 `resolver_trusted_mode=trusted_allow_all_modules` 时，系统 MUST 要求环境变量 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`，否则 MUST fail-fast。

该门控用于防止误在生产环境中启用“等效代码执行权限”的模式。

#### Scenario: trusted_allow_all_modules fails without env gate
- **WHEN** 调用方启用 `resolver_trusted_mode=trusted_allow_all_modules`
- **AND** 未设置 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 明确指出需要设置环境变量才能启用

#### Scenario: trusted_allow_all_modules allowed with env gate
- **WHEN** 调用方启用 `resolver_trusted_mode=trusted_allow_all_modules`
- **AND** 设置 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`
- **THEN** 系统 MAY 继续执行
- **AND** 系统 MUST 发出明确的风险告警（warning）
