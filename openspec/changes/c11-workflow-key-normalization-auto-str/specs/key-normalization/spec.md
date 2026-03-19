## ADDED Requirements

### Requirement: `key_normalization=auto_str` MUST normalize match keys via `auto_str_normalize`
系统 MUST 提供一个 opt-in 的 key 规范化策略 `key_normalization=auto_str`。

当启用该策略时，框架内部所有“需要匹配”的 key（例如 relations lookup key、derived outputs 的 `group_by`/`dedup_by` key）MUST 逐字段应用 `auto_str_normalize` 后再参与匹配。

并且：

- 用户显式配置的 cast（例如 relations 的 `lookup_cast` / source 的 `key.cast`）MUST 始终优先于 `key_normalization` 的缺省策略。

#### Scenario: relations lookup key `"1"` and `1` are treated as the same key when enabled
- **GIVEN** relations 需要查找的 raw key 值为 `1`
- **AND** 上游数据源在关系映射中使用了字符串 key `"1"`
- **WHEN** 用户启用 `key_normalization=auto_str`
- **AND** 未对该 lookup 配置 `lookup_cast`/`key.cast`
- **THEN** 系统 MUST 将 `1` 规范化为稳定字符串并命中 `"1"` 的映射

#### Scenario: derived outputs group_by merges semantically equal keys when enabled
- **GIVEN** derived outputs 的 `group_by` 字段在不同输入行中分别为 `1` 与 `"1"`
- **WHEN** 用户启用 `key_normalization=auto_str`
- **THEN** 系统 MUST 将两者规范化为相同的分组 key，从而落入同一分组
