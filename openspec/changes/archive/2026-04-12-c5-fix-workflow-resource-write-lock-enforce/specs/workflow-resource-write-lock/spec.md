# workflow-resource-write-lock Specification

## Purpose

修复 workflow 资源输出 `write_lock` 配置未在 publish 阶段生效的问题，确保当用户显式启用写锁时不会发生“静默覆盖”。

## ADDED Requirements

### Requirement: Workflow resource publish MUST enforce write_lock at final_path

当 workflow 资源输出声明 `write_lock=true`（例如 `resources.books.<id>.write_lock` 或 `resources.books.<id>.export_xlsx.write_lock`）时，系统 MUST 在 publish（staged → final）边界对目标 `final_path` 进行跨进程互斥。

#### Scenario: concurrent publish with write_lock fails fast

- **GIVEN** 两个独立 workflow 进程将输出发布到同一 `final_path`
- **AND** 该输出启用了 `write_lock=true`
- **WHEN** 两个 workflow 在 publish 阶段并发尝试写入该 `final_path`
- **THEN** 系统 MUST 允许其中一个 workflow 完成 publish
- **AND** 系统 MUST 使另一个 workflow fail-fast，并抛出可诊断的写入异常
- **AND** 异常信息 MUST 包含 `lock_path`（即 `<final_path>.scalim.lock`）以及可用的 lock owner 信息（例如 `workflow_exec_id`）

### Requirement: write_lock=false MUST NOT introduce lock conflicts

当输出未启用 `write_lock`（默认）时，系统 MUST NOT 因为 lockfile 冲突而拒绝 publish。

#### Scenario: publish without write_lock does not fail due to locking

- **GIVEN** 两个 workflow 进程将输出发布到同一 `final_path`
- **AND** 该输出未启用 `write_lock`（等价于 `write_lock=false`）
- **WHEN** 两个 workflow 在 publish 阶段发生并发或交错执行
- **THEN** 系统 MUST NOT 因 lockfile 冲突而 fail-fast
- **AND** 最终文件内容 MAY 由最后完成 publish 的 workflow 覆盖（“最后写入者胜”）
