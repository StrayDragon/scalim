# yaml-dsl-allowlist-policy Specification

## Purpose
防止allowlist配置误用导致的安全风险，包括通配符滥用、隐式逃逸口和不受信的trusted-mode启用。

## Related Concepts
- Allowlist策略模块 (allowlist_policy)
- Trusted模式门控 (trusted_mode)
- 环境变量门控机制 (env_var_gates)

## Requirements

### Requirement: wildcard restrictions
系统MUST拒绝allowlist中的通配符配置，除非显式启用trusted-mode。`allowed_modules`和`allowed_functions`的通配符处理规则不同。

#### Scenario: allowed_modules wildcard rejected by default
- **GIVEN** 调用方未启用trusted-mode
- **WHEN** 运行入口收到`allowed_modules={"*"}`
- **THEN** 系统MUST fail-fast
- **AND** 错误信息MUST指出通配符默认被禁止并提供迁移建议（trusted-mode或显式allowlist）

#### Scenario: allowed_functions wildcard always rejected
- **WHEN** 运行入口收到`allowed_functions={"*"}`（无论trusted-mode状态）
- **THEN** 系统MUST fail-fast
- **AND** 错误信息MUST提示使用仅`allowed_modules`或trusted-mode替代

#### Scenario: trusted-mode enables wildcard with warnings
- **GIVEN** 调用方显式启用trusted-mode
- **WHEN** 运行入口收到`allowed_modules={"*"}`（或等价全放开配置）
- **THEN** 系统MUST允许继续执行
- **AND** 系统MUST发出风险告警（至少warning级）

### Requirement: trusted-mode gating and warnings
系统MUST通过多层门控防止trusted-mode误启用，包括显式参数、环境变量和强风险告警。

#### Scenario: trusted-mode requires explicit enablement
- **WHEN** 调用方未显式启用trusted-mode相关参数
- **THEN** 系统MUST不允许放宽allowlist约束
- **AND** 系统MUST NOT发出与trusted-mode相关的告警

#### Scenario: trusted_allow_all_modules requires env var gate
- **WHEN** 调用方启用`resolver_trusted_mode=trusted_allow_all_modules`
- **AND** 未设置`SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`
- **THEN** 系统MUST fail-fast
- **AND** 错误信息MUST明确指出需要设置环境变量

#### Scenario: trusted_allow_all_modules allowed with env gate
- **GIVEN** 调用方启用`resolver_trusted_mode=trusted_allow_all_modules`
- **AND** 设置`SCALIM_ALLOW_TRUSTED_ALL_MODULES=1`
- **THEN** 系统MAY继续执行
- **AND** 系统MUST发出明确的风险告警

### Requirement: denylist-only escape hatches
系统MUST NOT提供隐式逃逸口子绕过allowlist要求。allowlist缺失时MUST fail-fast并提供修复示例。

#### Scenario: missing allowlist fails fast
- **WHEN** 调用方未提供`allowed_modules`且未提供`allowed_functions`
- **THEN** 系统MUST fail-fast
- **AND** 错误信息MUST提供可复制的allowlist配置示例

#### Scenario: denylist-only mode requires explicit unsafe flag
- **GIVEN** 系统提供denylist-only（不安全）模式支持内部测试
- **WHEN** 调用方尝试启用denylist-only模式
- **THEN** 系统MUST要求显式unsafe参数（命名包含`unsafe`或等价标识）
- **AND** 系统MUST NOT通过环境变量隐式改变行为
- **AND** denylist-only模式MUST与allowlist/trusted-mode互斥

### Requirement: resolver MUST enforce denylist during attribute traversal (including trusted mode)
即使在 `resolver_trusted_mode=trusted_allow_all_modules` 放宽模块 allowlist 的情况下,Python 引用解析器也 MUST 对危险模式保持 denylist 防御深度。

系统 MUST 在解析 class-style 引用的属性链遍历过程中逐级执行 denylist 校验:
- 属性名命中危险函数列表(例如 `getattr/open/eval/...`) MUST fail-fast
- 属性名包含 `__` 或等价自省危险模式 MUST fail-fast
- 属性名为 `lambda` MUST fail-fast

该要求的目的是 defense-in-depth: 即使未来上游对“引用字符串”的校验逻辑调整,遍历实现本身也不应变成可被利用的空窗。

#### Scenario: dangerous attribute name is rejected in class-style traversal
- **WHEN** 引用包含属性链片段命中 denylist(例如 `pkg.mod:Obj.getattr`)
- **THEN** resolver MUST fail-fast

#### Scenario: dunder attribute is rejected in traversal
- **WHEN** 引用包含 `__` 相关属性(例如 `pkg.mod:Obj.__class__`)
- **THEN** resolver MUST fail-fast
