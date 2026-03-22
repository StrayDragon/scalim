## MODIFIED Requirements

### Requirement: `key_normalization` EXPERIMENTAL warning MUST be visible by default

当用户启用 `key_normalization` 的非 `raw` 模式时,系统 MUST 在一次运行内至少发出一次包含 `EXPERIMENTAL` 的提示,且该提示在默认配置下 MUST 可见(不要求用户额外挂载 observer/hook,也不要求显式开启 fallback logger)。

该提示仍需满足原有约束:

- MUST 包含当前启用的 `key_normalization` 值
- MUST NOT 包含任何明细 key 值
- SHOULD 在一次运行内去重(避免刷屏)

#### Scenario: enabling key_normalization emits a visible experimental warning by default
- **GIVEN** 调用方启用 `key_normalization="auto_str"`(或 `"force_str"`)
- **AND** 调用方未注册任何 observer/hook,也未显式开启 fallback logger
- **WHEN** 系统开始运行
- **THEN** 系统 MUST 发出一次包含 `EXPERIMENTAL` 的提示,且该提示在默认配置下可见

