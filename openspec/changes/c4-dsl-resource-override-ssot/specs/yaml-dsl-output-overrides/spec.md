## ADDED Requirements

### Requirement: demand compile and workflow compile MUST share the same overrides compilation pipeline

系统 MUST 仅保留一套 overrides 解析/校验实现(SSOT),并同时服务于:
- 单 demand runtime compile (`compile/run`)
- workflow compile (`compile_workflow` 等)

系统 MUST NOT 维护两份“语义等价但实现不同”的 overrides parser/validator,以避免规则漂移与修复遗漏。

#### Scenario: override validation behavior stays consistent across entrypoints
- **GIVEN** 某个非法的 `RunOverrides.outputs`(例如 to.file 与 to.book/to.sheet 互斥冲突)
- **WHEN** 调用方分别在 demand compile 与 workflow compile 路径触发该校验
- **THEN** 两条路径 MUST 都 fail-fast
- **AND** 报错类型 MUST 一致

### Requirement: invalid overrides MUST raise ScalimWorkflowConfigError with stable path

当 overrides/resources/outputs_defaults/output_extras 的输入非法时,系统 MUST 抛出 `ScalimWorkflowConfigError` 并提供稳定可定位的 `path=`。

#### Scenario: invalid typed overrides fails with ScalimWorkflowConfigError
- **WHEN** 调用方提供非法的 typed overrides
- **THEN** 系统 MUST 抛 `ScalimWorkflowConfigError`
- **AND** `path` MUST 指向可定位的逻辑路径(例如 `overrides.outputs.0.to` 或 `overrides.outputs_defaults.to.book`)
