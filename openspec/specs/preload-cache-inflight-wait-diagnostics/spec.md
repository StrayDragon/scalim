# preload-cache-inflight-wait-diagnostics Specification

## Purpose
TBD - created by archiving change c75-preload-cache-inflight-wait-diagnostics. Update Purpose after archive.
## Requirements
### Requirement: inflight wait diagnostics MUST be opt-in and include stable fields
系统 MUST 提供 inflight 等待诊断能力，且默认关闭；仅在显式开启后生效。

在诊断模式开启时，当等待 inflight 超过阈值，系统 MUST 输出诊断信号，并包含稳定字段（至少包含 `source_id` 与 `wait_s`）。

诊断信号 SHOULD 遵循框架日志约定：

- 前缀：`[scalim] preload-cache:`
- 字段：稳定 `k=v`（至少 `source_id=<...> wait_s=<...>`），便于 grep/监控聚合

#### Scenario: long inflight wait emits warning only when diagnostics enabled
- **GIVEN** preload cache inflight wait diagnostics 已显式开启
- **WHEN** 某线程等待 inflight 的时间超过阈值
- **THEN** 系统 MUST 输出一次 warning 诊断信号
- **AND** warning MUST 包含稳定字段 `source_id` 与 `wait_s`

