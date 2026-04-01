## MODIFIED Requirements

### Requirement: joinable get-or-create 的等待诊断
系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 wait diagnostics,使 waiter 等待过程可观测且可定位.
该诊断配置 MUST 作为 workflow-level SSOT 暴露(例如 `workflow.options.resources_wait`),并贯穿 YAML→IR→runtime.

约束:

- 诊断配置 MUST 包含 `diagnostics.enabled`(默认 false)
- 当 `diagnostics.enabled=true` 时,诊断配置 MUST 包含 `warn_after_s`(首次告警阈值)和可选的 `repeat_every_s`(重复告警间隔)
- 告警 MUST 包含: `resource_id`、owner 线程标识、waiter 线程标识、已等待时长
- 当启用 `capture_owner_callsite=true` 时,告警 SHOULD 额外包含 owner callsite(用于定位卡住的创建点)
- 告警 MUST 走 instrumentation event 或 warning logger,不得污染正常输出
- 默认行为 MUST 为禁用(仅在 `diagnostics.enabled=true` 时输出告警)

#### Scenario: waiter 等待超过阈值时产生诊断告警
- **GIVEN** wait diagnostics 启用且 `warn_after_s=5.0`
- **WHEN** waiter 等待 owner 创建资源超过 5 秒
- **THEN** 系统 MUST 发出包含 resource_id/owner_thread/waiter_thread/wait_s 的告警

### Requirement: joinable get-or-create 的可选超时
系统 MUST 为共享资源的 joinable get-or-create 提供 max wait / fail-fast 能力,以避免并发场景无限等待导致 workflow hang.

约束:

- 超时后 MUST 以 `WorkflowWriteError` 失败,错误消息包含 resource_id、owner 线程标识、已等待时长与 max_wait_s
- 默认策略 MUST 为启用超时且 `max_wait_s=600`(BREAKING: 不再允许无限等待作为默认)
- 超时值 MUST 可配置(优先通过 workflow-level 配置 `workflow.options.resources_wait.max_wait_s`)
- 若显式将 `max_wait_s` 配置为 `0` 或负数,MUST 被拒绝并给出配置错误

#### Scenario: owner 卡死导致 waiter 超时
- **GIVEN** max_wait_s 配置为 60 秒
- **WHEN** owner 线程创建资源超过 60 秒未完成
- **THEN** waiter MUST 以包含诊断信息的 `WorkflowWriteError` 失败

#### Scenario: default timeout is enforced
- **GIVEN** 未显式配置 max_wait_s
- **WHEN** owner 线程创建资源超过默认超时
- **THEN** waiter MUST fail-fast,而不是无限等待
