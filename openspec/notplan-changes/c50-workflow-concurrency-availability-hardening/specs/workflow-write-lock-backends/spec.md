## ADDED Requirements

### Requirement: workflow shared outputs MUST support configurable write-lock backends

系统 MUST 为 workflow 共享输出资源的最终写入提供可选写锁后端,以适配不同文件系统语义与部署环境.

约束:

- 系统 MUST 至少支持以下后端枚举：`file`、`mkdir`、`none`
- 后端选择 MUST 为 workflow-scope 配置,并对同一 workflow 内所有共享输出（csv/workbook/sheetbook/books export）一致生效
- 当后端为 `none` 时,系统 MUST 明确“不提供并发写入互斥保障”

#### Scenario: backend selection passes through workflow execution
- **WHEN** 用户将 workflow 写锁后端配置为 `mkdir`
- **THEN** workflow runtime 对共享输出的写锁获取 MUST 使用 `mkdir` 语义
- **AND** 锁冲突诊断中 MUST 能体现所使用的 backend

### Requirement: lock conflicts MUST provide actionable diagnostics

当获取写锁失败（可能存在并发写入方）时,系统 MUST 在错误中提供可操作诊断,以支持定位与治理.

约束:

- 错误信息 MUST 包含：`lock_path`、`backend`、以及 best-effort 的 owner 信息（pid/hostname/workflow_exec_id/resource_id 等）
- 若可获取锁 mtime（或等价时间信息）,诊断 SHOULD 包含 `lock_age_s`
- 错误信息 MUST 提供可执行 hint（例如 “delete lock path if safe”）,但 MUST 明确风险（仅在确认无 writer 时操作）

#### Scenario: conflict error includes owner info and hint
- **GIVEN** 某个输出路径已被另一 writer 持有写锁
- **WHEN** 第二个 writer 尝试获取同一输出路径的写锁
- **THEN** 系统 MUST fail-fast
- **AND** 错误 diff MUST 包含 owner 信息与治理 hint

### Requirement: stale lock reclamation MUST be explicit and guarded

系统 MUST 支持对“疑似陈旧锁”的显式治理,用于处理 writer 崩溃导致的锁残留；该能力 MUST 默认关闭并具备防误删约束.

约束:

- stale reclaim MUST 仅在 `stale_after_s` 与 `force=true` 均显式设置时启用
- 系统 MUST 仅在观测到 `lock_age_s >= stale_after_s` 时才允许回收锁
- 若无法获取 lock_age,系统 MUST NOT 回收锁（避免误删）

#### Scenario: reclaim requires stale age threshold
- **GIVEN** `stale_after_s=60` 且 `force=true`
- **AND** lock_age_s=10
- **WHEN** writer 尝试获取锁
- **THEN** 系统 MUST NOT 回收该锁
- **AND** 仍应以包含诊断信息的错误失败

### Requirement: mkdir backend MUST use atomic directory creation

当后端为 `mkdir` 时,系统 MUST 通过原子目录创建实现互斥语义,并以目录内的 owner 文件记录诊断信息.

约束:

- 锁 MUST 以“目录存在”表达持有态（例如 `<output_path>.scalim.lock.d/`）
- 锁目录创建 MUST 为原子操作（例如 `mkdir` 失败表示已被占用）
- release MUST 删除锁目录（best-effort 清理目录内 owner 信息文件）

#### Scenario: mkdir backend prevents concurrent writers
- **WHEN** 两个并发 writer 尝试对同一输出路径获取 `mkdir` 写锁
- **THEN** 至多一个 writer 能获取锁
- **AND** 另一个 writer MUST 以包含 owner 信息的冲突错误失败

