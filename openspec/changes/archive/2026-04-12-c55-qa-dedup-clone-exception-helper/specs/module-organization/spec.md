# module-organization (delta) Specification

## ADDED Requirements

### Requirement: cross-cutting internal helpers MUST have a single SSOT implementation without layer inversion

当同一类“基础设施级”逻辑被多个领域模块复用（例如 execution/workflow 都需要的异常 clone、线程等待诊断、路径处理等）时，系统 MUST 避免复制粘贴式的重复实现，并满足：

- 系统 MUST 将该逻辑抽取到单一 SSOT 内部 util 模块（例如 `_internal/utils/`），作为权威实现
- 该 util 模块 MUST 保持低耦合（不得依赖更高层领域模块），避免形成层级反转或循环依赖
- 测试口径 MUST 覆盖该 SSOT util，而不是只覆盖某个领域模块的副本

#### Scenario: exception clone helper is centralized
- **GIVEN** workflow 与 execution 两条路径都需要“跨线程传播异常”的 clone 逻辑
- **WHEN** 维护者实现该能力
- **THEN** 仓库 MUST 只有一份权威的 `clone_exception_for_reraise`（或等价）实现
- **AND** workflow/execution 调用点 MUST 导入该 SSOT util 而不是各自维护副本

