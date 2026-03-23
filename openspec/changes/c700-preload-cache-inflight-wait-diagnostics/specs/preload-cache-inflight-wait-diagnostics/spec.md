# preload-cache-inflight-wait-diagnostics Specification

## Purpose
为 preload cache inflight 等待提供**可选诊断能力**：在显式开启诊断模式时，当等待时间异常偏长，应输出稳定且可聚合的诊断信号，帮助快速定位卡住的 `source_id` 与等待时长。

## ADDED Requirements

### Requirement: inflight wait diagnostics MUST be opt-in and include stable fields
系统 MUST 提供 inflight 等待诊断能力，且默认关闭；仅在显式开启后生效。

在诊断模式开启时，当等待 inflight 超过阈值，系统 MUST 输出诊断信号，并包含稳定字段（至少包含 `source_id` 与 `wait_s`）。

#### Scenario: long inflight wait emits warning only when diagnostics enabled
- **GIVEN** preload cache inflight wait diagnostics 已显式开启
- **WHEN** 某线程等待 inflight 的时间超过阈值
- **THEN** 系统 MUST 输出一次 warning 诊断信号
- **AND** warning MUST 包含稳定字段 `source_id` 与 `wait_s`

