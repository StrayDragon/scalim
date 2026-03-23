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

### Requirement: relations mapping collisions after normalization MUST be handled safely by default

当 relations 在构建“规范化后的 mapping 视图”时,若多个不同 raw key 规范化到同一个稳定字符串 key(即发生 collision),系统 MUST 按以下规则安全处理:

- 若 collision 对应的 value 全部 `==`(深度相等),系统 MUST 保留任一值并继续(并发出一次 redacted 告警,便于用户后续清理 loader/data)
- 若 collision 对应的 value 存在差异,系统 MUST fail-fast(避免 silent 选择导致隐性错误)

并且:

- 告警/错误文案 MUST NOT 包含任何明细 key 值
- 告警/错误文案 SHOULD 包含 source/loader 标识、`key_normalization` 模式、collision 计数等上下文信息

#### Scenario: collision with identical values continues with a redacted warning
- **GIVEN** 启用 `key_normalization="force_str"`(或满足进入字符串规范化 key space 的条件)
- **AND** loader 返回的 mapping 同时包含 key `1` 与 `"1"`,且两者规范化后 collision
- **AND** 两个 key 对应的 value 深度相等(`==`)
- **WHEN** 系统构建规范化 mapping 视图并执行 relations lookup
- **THEN** 系统 MUST 继续执行并命中该 mapping
- **AND** 系统 SHOULD 发出一次 redacted 告警提示发生了可安全合并的 collision

#### Scenario: collision with different values fails fast
- **GIVEN** 启用 `key_normalization="force_str"`(或满足进入字符串规范化 key space 的条件)
- **AND** loader 返回的 mapping 同时包含 key `1` 与 `"1"`,且两者规范化后 collision
- **AND** 两个 key 对应的 value 不相等(`!=`)
- **WHEN** 系统构建规范化 mapping 视图
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST NOT 包含明细 key 值

### Requirement: loader mapping key-space mismatches MUST be diagnosable and redacted

当 `key_normalization` 与显式 cast(例如 `lookup_cast`/`key.cast`)组合导致“预期 key 口径”与 loader mapping 的实际 key 口径不一致时,系统 MUST 提供可诊断的告警/错误,并满足:

- MUST NOT 泄露明细 key 值
- SHOULD 提供可操作的修复建议(例如调整 cast、改用 `force_str`、统一 loader key 口径)

#### Scenario: auto_str with explicit cast hits only after normalization emits a redacted warning
- **GIVEN** `key_normalization="auto_str"`
- **AND** 存在显式 `lookup_cast`/`key.cast`,使得最终候选 key 口径为非字符串(例如 `int`)
- **AND** loader 返回的 mapping key 口径为字符串(例如 `"1"`)
- **WHEN** 系统发现 cast 后候选 key 命中失败,但对候选 key 做字符串规范化后可以命中
- **THEN** 系统 SHOULD 发出 redacted 告警提示存在 key 口径错配
- **AND** 告警 SHOULD 提示调整 cast 或改用 `force_str`
