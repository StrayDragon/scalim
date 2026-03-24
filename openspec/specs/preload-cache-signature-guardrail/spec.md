# preload-cache-signature-guardrail Specification

## Purpose
TBD - created by archiving change c700-preload-cache-signature-guardrail. Update Purpose after archive.
## Requirements
### Requirement: signature mismatch MUST be detectable when guardrail enabled
系统 MUST 为 `PreloadCache` 提供可选 guardrail 开关（默认关闭）,并在开启时检测同一 `source_id` 的 signature 冲突:

- 系统 MUST 支持至少两种策略: `error|warn`
- 当检测到同一 `source_id` 的 signature 不一致时:
  - `error`: MUST fail-fast
  - `warn`: MUST 产生强告警,且继续执行
- 诊断信息 MUST 可用于定位与迁移（至少包含 `source_id`、两次 signature digest、以及差异字段摘要或迁移提示）

#### Scenario: signature mismatch fails fast in `error` mode
- **GIVEN** 共享同一个 `PreloadCache`
- **AND** 该 `PreloadCache` 已缓存 `source_id="s1"` 的结果,其 signature digest 为 A
- **WHEN** 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
- **AND** guardrail 策略为 `error`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 包含 `source_id="s1"` 与 A/B 的差异诊断

#### Scenario: signature mismatch warns in `warn` mode
- **GIVEN** 共享同一个 `PreloadCache`
- **AND** 该 `PreloadCache` 已缓存 `source_id="s1"` 的结果,其 signature digest 为 A
- **WHEN** 再次请求 `source_id="s1"` 且本次 signature digest 为 B（A!=B）
- **AND** guardrail 策略为 `warn`
- **THEN** 系统 MUST 产生强告警且继续执行

### Requirement: default behavior MUST remain unchanged when guardrail disabled
当 guardrail 关闭时,系统 MUST 保持既有语义（按 `source_id` key 做 per-key `in-flight` 去重与结果复用）,不得因 guardrail 的引入改变默认行为或引入新的数据竞态/死锁。

#### Scenario: guardrail disabled keeps legacy semantics
- **WHEN** guardrail 未开启
- **THEN** `PreloadCache.get_or_load(source_id, ...)` 的 key MUST 仍为 `source_id`
- **AND** 同一 `source_id` 并发请求 MUST 仍只触发一次实际 `load_fn`

