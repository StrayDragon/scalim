## ADDED Requirements

### Requirement: joinable get-or-create 的等待诊断
系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 wait diagnostics,使 waiter 等待过程可观测且可定位.

约束:
- 诊断配置 MUST 包含 `warn_after_s`(首次告警阈值)和可选的 `repeat_every_s`(重复告警间隔)
- 告警 MUST 包含: `resource_id`、`resource_type`、owner 线程标识、waiter 线程标识、已等待时长
- 告警 MUST 走 instrumentation event 或 warning logger,不得污染正常输出
- 默认行为 MUST 为禁用(避免行为变化)

#### Scenario: waiter 等待超过阈值时产生诊断告警
- **GIVEN** wait diagnostics 启用且 `warn_after_s=5.0`
- **WHEN** waiter 等待 owner 创建资源超过 5 秒
- **THEN** 系统 MUST 发出包含 resource_id/owner_thread/waiter_thread/wait_s 的告警

#### Scenario: 重复告警
- **GIVEN** wait diagnostics 启用且 `repeat_every_s=10.0`
- **WHEN** waiter 持续等待
- **THEN** 系统 MUST 每隔 `repeat_every_s` 重复告警(首次在 `warn_after_s` 时)

### Requirement: joinable get-or-create 的可选超时
系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 max wait / fail-fast 能力.

约束:
- 超时后 MUST 以 `WorkflowWriteError` 失败,错误消息包含 resource_id、owner 线程标识、已等待时长
- 默认策略 MUST 为"仅告警不超时"(避免行为变化)
- 超时值 MUST 可配置(建议通过 workflow-level 配置或环境变量)

#### Scenario: owner 卡死导致 waiter 超时
- **GIVEN** max_wait_s 配置为 60 秒
- **WHEN** owner 线程创建资源超过 60 秒未完成
- **THEN** waiter MUST 以包含诊断信息的 `WorkflowWriteError` 失败

### Requirement: commit_all/discard_all 与 inflight 并发交错语义
系统 MUST 在 `commit_all()`/`discard_all()` 执行时显式处理与 inflight 创建的并发交错,采用以下策略之一:

- **drain**(推荐): commit/discard 在开始前 MUST 等待所有 inflight 创建完成,保证不会"漏 commit / 漏 discard"
- **fail-fast**: 若检测到 inflight 非空,commit/discard MUST 失败并给出明确错误

约束:
- 选定策略 MUST 作为 SSOT 记录,不得留为隐式行为
- drain 模式下等待 MUST 复用 wait diagnostics(含 warn_after/timeout)

#### Scenario: commit_all 与 inflight 创建并发时 drain
- **GIVEN** 采用 drain 策略
- **WHEN** 某线程正在 inflight 创建资源,另一线程调用 `commit_all()`
- **THEN** `commit_all()` MUST 等待 inflight 创建完成后再 commit 所有资源

#### Scenario: commit_all 与 inflight 创建并发时 fail-fast
- **GIVEN** 采用 fail-fast 策略
- **WHEN** 某线程正在 inflight 创建资源,另一线程调用 `commit_all()`
- **THEN** `commit_all()` MUST 以明确错误失败(提示调用约束被破坏)
