## ADDED Requirements

### Requirement: execution contracts MUST be splittable from orchestration while preserving stable entrypoints
系统 MUST 允许将 execution 的 DSL-agnostic contracts(例如 `ExecutionRequest`/`ExecutionResult`)从 orchestration 逻辑中拆分到独立模块,以降低热点文件聚合度并改善可测试性。

同时系统 MUST 保持稳定入口不变:
- 既有 `run_ir` 稳定导入路径 MUST 继续可用
- contracts 在稳定入口处的导入路径 MUST 继续可用(可通过 re-export 兼容)

#### Scenario: existing run_ir imports remain stable after refactor
- **WHEN** 调用方通过既有稳定入口导入并调用 `run_ir`
- **THEN** 导入 MUST 成功且行为与重构前一致
