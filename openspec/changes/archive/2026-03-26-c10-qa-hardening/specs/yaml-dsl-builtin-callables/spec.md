## ADDED Requirements

### Requirement: builtin_callables vocabulary values MUST obey allowlist when expressed as Python references
当调用方通过 `builtin_callables` 词表配置将 `<id>` 映射为 Python 引用字符串（例如 `module.path:function`）时，系统 MUST 使用与主 resolver 一致的 allowlist 策略解析该引用（不得进入“仅 denylist”或“任意模块”解析模式）。

#### Scenario: builtin_callables reference string is rejected if not allowlisted
- **GIVEN** 调用方提供 `builtin_callables={"x": "pkg.mod:fn"}`
- **WHEN** allowlist 未允许 `pkg.mod`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 可操作（提示配置 allowlist 或直接传入 callable）

#### Scenario: builtin_callables accepts direct callables without allowlist expansion
- **GIVEN** 调用方提供 `builtin_callables={"x": <callable>}`
- **WHEN** YAML 引用 `^x`
- **THEN** 系统 MUST 解析成功且不要求将 `scalim.*` 加入 allowlist
