# execution-adaptive-guardrails Specification

## Purpose
TBD - created by archiving change c0-deps-and-adaptive-guardrails. Update Purpose after archive.
## Requirements
### Requirement: explicit max_workers MUST be guarded by a hard cap
当调用方显式传入 `max_workers > 0` 时，系统 MUST 对其施加 hard cap，避免因外部输入不受控而导致线程池膨胀、CPU/内存资源耗尽。

系统 MUST 同时满足：
- cap 策略是稳定且可解释的（例如与 `os.cpu_count()` 相关，并有上限）
- 当发生裁剪（`resolved_workers < requested_workers`）时，系统 MUST 发出可诊断的 warning/事件/日志（不得静默）

#### Scenario: extreme worker request is capped and warned
- **GIVEN** 用户/配置传入极端的 `max_workers`（例如 `10000`）
- **WHEN** 系统解析并创建 adaptive thread pool
- **THEN** 系统 MUST 将其裁剪到 hard cap
- **AND** 系统 MUST 发出可诊断的 warning/事件/日志，说明 requested 与 resolved 值

### Requirement: adaptive execution MUST support an optional task timeout for fail-fast diagnostics
系统 MUST 支持为 adaptive 任务等待路径配置可选 timeout（默认关闭）。

当 timeout 启用且等待超过阈值时，系统 MUST：
- fail-fast（抛出明确异常，而非无限等待）
- 提供可定位的诊断信息（至少包含未完成任务 keys/数量，以及建议排查点）

#### Scenario: timeout fails fast with actionable diagnostics
- **GIVEN** 启用了 adaptive 任务 timeout
- **WHEN** 某个 loader/用户任务长时间无返回
- **THEN** 系统 MUST 抛出明确的 timeout 异常
- **AND** 异常信息 MUST 包含未完成任务的定位线索

