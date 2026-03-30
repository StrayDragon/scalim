## MODIFIED Requirements

### Requirement: joinable get-or-create 的可选超时
系统 MUST 为共享资源的 joinable get-or-create 提供 max wait / fail-fast 能力,并默认启用有限超时以避免 workflow 无限挂起.

约束:

- 超时后 MUST 以 `WorkflowWriteError` 失败,错误消息包含 resource_id、owner 线程标识、已等待时长
- 默认策略 MUST 为“启用超时”（默认 `max_wait_s=600`）,并允许在 workflow-level 配置中调整阈值
- 超时值 MUST 可配置且 MUST 为有限的非负数（不得通过 `null/None` 表达无限等待）

#### Scenario: owner 卡死导致 waiter 超时
- **GIVEN** max_wait_s 配置为 60 秒
- **WHEN** owner 线程创建资源超过 60 秒未完成
- **THEN** waiter MUST 以包含诊断信息的 `WorkflowWriteError` 失败

#### Scenario: default max_wait_s is applied when not configured
- **GIVEN** workflow 未显式配置 max_wait_s
- **WHEN** waiter 等待 inflight 创建超过默认阈值
- **THEN** waiter MUST fail-fast
- **AND** 错误信息 MUST 包含 `max_wait_s=600` 的诊断字段

