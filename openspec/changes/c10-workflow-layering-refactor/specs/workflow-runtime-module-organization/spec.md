## MODIFIED Requirements

### Requirement: workflow runtime MUST be modularized while preserving stable entrypoints
系统 MUST 将 workflow runtime 作为 framework 层能力放置在独立包中(SSOT: `IMPL_ROOT.workflow`),并按职责拆分为更小的内部模块（例如 execute/scheduler、ctx、resources、loaders、report）。

系统 MUST 同时保持 YAML workflow 的稳定入口可用(SSOT: `IMPL_ROOT.dsl.by_yaml.workflow_entrypoints`),调用方不需要因内部拆分而修改导入路径。

#### Scenario: stable workflow entrypoints remain importable after refactor
- **WHEN** 调用方导入并调用 workflow 的稳定入口（例如 `run_workflow`）
- **THEN** 导入 MUST 成功且行为与重构前一致

