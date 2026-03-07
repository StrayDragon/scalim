# hooks-events Specification

## Purpose
TBD - created by archiving change add-loader-retry-policy. Update Purpose after archive.
## Requirements
### Requirement: 新增 `loader_retry` 事件用于观测重试尝试
系统 SHALL 新增事件类型 `loader_retry`,用于表达“某次 loader 调用失败且系统决定按 policy 重试”.
系统 MUST 在每次 retry runner 决定进入 sleep+下一次尝试之前发出该事件.
系统 MUST NOT 将每次可重试失败当作 `error` 事件;`error` 事件仅用于最终失败(不再重试)或不可重试错误.

`loader_retry` payload MUST 至少包含:
- `loader_name`(或 `source_id`,两者语义等价)
- `callsite`(load/load_ref/preload_forever/main_source 或等价枚举)
- `attempt_num`、`max_attempts`
- `elapsed_seconds`
- `sleep_seconds`(下一次尝试前的等待时长)
- `error_type`(异常类型名)与可选的截断 `error_message`

#### Scenario: 可重试失败触发 loader_retry 而非 error
- **WHEN** loader 抛出异常且 `should_retry` 返回 true 且未超过上限
- **THEN** 系统 MUST 发出一次 `loader_retry` 事件并进入 sleep+重试
- **AND** 不得在该次失败上发出 `error` 事件
