## ADDED Requirements

### Requirement: workflow write locks MUST support selectable backends
系统 MUST 为 workflow 共享输出的写锁提供可选后端,并以 workflow-level 配置作为 SSOT:

- `backend` MUST 支持: `file`、`mkdir`、`none`
- `file` 后端 MUST 使用排他创建语义创建锁文件,并写入 owner 元信息(至少 pid/created_at/hostname)
- `mkdir` 后端 MUST 使用原子目录创建语义作为锁（更适合 NFS/共享盘）
- `none` 后端 MUST 禁用写锁,并要求用户/平台外部保证互斥写入

#### Scenario: file backend rejects concurrent writers
- **GIVEN** `backend=file`
- **WHEN** 两个并发写入方尝试获取同一 output path 的写锁
- **THEN** 其中一个 MUST 成功,另一个 MUST 失败并给出 owner 信息与治理 hint

#### Scenario: mkdir backend uses atomic directory lock
- **GIVEN** `backend=mkdir`
- **WHEN** 写入方尝试获取写锁
- **THEN** 系统 MUST 通过原子 `mkdir` 成功或失败(不得先检查再创建导致 TOCTOU)

### Requirement: write lock governance MUST support stale reclaim with explicit force
系统 MUST 支持对 stale lock 的治理能力:

- 配置 MUST 支持 `stale_after_s`(非负浮点)与 `force`(bool)
- 当 lock age >= `stale_after_s` 且 `force=true` 时,系统 MAY 尝试回收 stale lock 并重试获取
- 当无法安全回收时,系统 MUST fail-fast 并在错误中包含:
  - lock path
  - lock age
  - stale_after_s/force 值
  - 治理 hint(例如“确认无并发写入后删除 lock”)

#### Scenario: force reclaim removes stale lock
- **GIVEN** 存在 stale lock 且 `stale_after_s` 已超时
- **AND** `force=true`
- **WHEN** 写入方尝试获取写锁
- **THEN** 系统 SHOULD 回收 stale lock 并成功获取

### Requirement: lock errors MUST be diagnosable
系统 MUST 保证写锁相关错误可诊断且可定位问题根因:

- 错误 MUST 包含 output path 与 lock path
- 错误 SHOULD 包含 owner 元信息(若可读取)
- 错误 MUST 给出明确的 mitigation hint(例如切换后端/调整 stale_after_s/外部协调)

#### Scenario: lock error includes mitigation hint
- **WHEN** 写锁获取失败
- **THEN** 错误信息 MUST 包含至少一个可执行的 mitigation hint
