# yaml-dsl-workflow Specification

## ADDED Requirements

### Requirement: `run_workflow(...)` MUST orchestrate parse/preload/effective-merge/preflight via a single lifecycle SSOT
为避免出现“多入口各自拼装生命周期”导致的 drift 与 workaround 修复点扩散，系统 MUST 将 workflow 生命周期的编排收敛为单一 SSOT（lifecycle pipeline），并要求 `run_workflow(...)` 复用该 SSOT：

- `run_workflow(...)` MUST 以 phase pipeline 的顺序执行关键阶段：parse、structural preload、effective merge、preflight、execute
- `run_workflow(...)` MUST NOT 跳过 preflight 直接启动 engine

#### Scenario: workflow execution always runs preflight before engine scheduling
- **GIVEN** workflow 存在某个可推理的 preflight 失败
- **WHEN** 用户调用 `run_workflow(...)`
- **THEN** 系统 MUST 在 engine 启动前直接 raise
- **AND** workflow engine MUST NOT 被启动

