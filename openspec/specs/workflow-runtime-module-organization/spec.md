# workflow-runtime-module-organization Specification

## Purpose
定义 workflow runtime 的包位置、子模块职责划分与稳定入口策略,确保其作为 framework 层能力与 DSL 层保持清晰边界.
## Requirements
### Requirement: workflow runtime MUST be modularized while preserving stable entrypoints
系统 MUST 将 workflow runtime 作为 framework 层能力放置在独立包中(SSOT: `IMPL_ROOT.workflow`),并按职责拆分为更小的内部模块（例如 execute/scheduler、ctx、resources、loaders、report）。

系统 MUST 同时保持 YAML workflow 的稳定入口可用(SSOT: `IMPL_ROOT.dsl.by_yaml.workflow_entrypoints`),调用方不需要因内部拆分而修改导入路径。

#### Scenario: stable workflow entrypoints remain importable after refactor
- **WHEN** 调用方导入并调用 workflow 的稳定入口（例如 `run_workflow`）
- **THEN** 导入 MUST 成功且行为与重构前一致

### Requirement: workflow visibility closure MUST have a single SSOT and be reused
workflow runtime 中所有依赖“节点可见性闭包”(transitive depends_on)的能力(至少包括 ctx refs 校验与 artifacts 可见性校验) MUST 复用单一 SSOT 的可见性索引/计算逻辑,避免重复实现导致的行为漂移.

#### Scenario: ctx and artifacts share the same visibility rules
- **GIVEN** workflow 节点 B depends_on A,且 C depends_on B(因此 C 传递可见 A)
- **WHEN** C 通过 ctx 或 artifacts 引用 A 的产物
- **THEN** 可见性判定 MUST 一致地视为可见
- **AND** 若缺失显式依赖导致不可见,错误 MUST 指向可诊断的配置路径并 fail-fast

