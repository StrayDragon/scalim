# execution-call-by-memoization Specification

## Purpose
TBD - created by archiving change c20-exp-call-by-memoize-field-policy. Update Purpose after archive.
## Requirements
### Requirement: Opt-in ctx-free call_by memoization

当且仅当启用实验性开关时，系统 MUST 对满足条件的 `ctx-free call_by` 派生字段启用“按字段 LRU”记忆化；默认 MUST 关闭。

#### Scenario: Disabled by default
- **WHEN** 未设置 `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES`（或其值为 `0`/负数）
- **THEN** 系统 MUST 不启用 `call_by` 记忆化（行为等价于未实现该特性）

#### Scenario: Enabled only for ctx-free call_by
- **WHEN** 设置 `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES` 为正整数
- **THEN** 系统 MUST 仅对“不需要 `$ctx` 注入”的 `call_by` 字段启用缓存候选
- **THEN** 系统 MUST 不对需要 `$ctx` 的 `call_by` 字段启用缓存候选

### Requirement: Field allow/deny filter for memoization

系统 MUST 提供字段级过滤策略，使用户可明确选择哪些字段参与 memoization、哪些字段被排除。

#### Scenario: Allow is empty means allow all candidates
- **WHEN** 未设置 `SCALIM_EXP_CALL_BY_MEMOIZE_ALLOW`（或解析结果为空）
- **THEN** 系统 MUST 将“未被 deny 排除的字段”视为缓存候选

#### Scenario: Allow restricts candidates
- **WHEN** `SCALIM_EXP_CALL_BY_MEMOIZE_ALLOW` 解析为非空 patterns 集合
- **THEN** 系统 MUST 仅将匹配任一 allow pattern 的字段视为缓存候选

#### Scenario: Deny overrides allow
- **WHEN** 某字段同时匹配 allow 与 deny patterns
- **THEN** 系统 MUST 将该字段排除出缓存候选

### Requirement: Bounded memory and safe semantics

系统 MUST 为 memoization 提供硬上限，并保持可预测的语义边界。

#### Scenario: Per-field hard cap
- **WHEN** `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES=N` 且 `N > 0`
- **THEN** 系统 MUST 将每个字段的缓存容量上限限制为 `N`（不得无界增长）

#### Scenario: Cache only successful calculator results before transform
- **WHEN** 某 `ctx-free call_by` 字段被启用 memoization
- **THEN** 系统 MUST 仅缓存 calculator 成功返回的结果
- **THEN** 系统 MUST 缓存 value transform 执行前的结果（transform 作为后置处理每次仍可执行）

### Requirement: Optional performance logging for ROI

系统 MUST 提供实验性日志开关，以 `scalim.performance` 输出 memoization 的聚合统计，用于线上判断 ROI；默认 MUST 不输出。

#### Scenario: Logging is opt-in
- **WHEN** 未启用 `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS`
- **THEN** 系统 MUST 不输出 memoization 聚合统计日志

#### Scenario: Logging is privacy-preserving
- **WHEN** 启用 `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS`
- **THEN** 系统 MUST 仅输出字段级聚合计数/比率等元信息
- **THEN** 系统 MUST NOT 输出任何依赖值本身（例如具体 dep tuple/value）

