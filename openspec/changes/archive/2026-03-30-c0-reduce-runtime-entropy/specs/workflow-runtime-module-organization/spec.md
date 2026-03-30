## ADDED Requirements

### Requirement: workflow visibility closure MUST have a single SSOT and be reused
workflow runtime 中所有依赖“节点可见性闭包”(transitive depends_on)的能力(至少包括 ctx refs 校验与 artifacts 可见性校验) MUST 复用单一 SSOT 的可见性索引/计算逻辑,避免重复实现导致的行为漂移.

#### Scenario: ctx and artifacts share the same visibility rules
- **GIVEN** workflow 节点 B depends_on A,且 C depends_on B(因此 C 传递可见 A)
- **WHEN** C 通过 ctx 或 artifacts 引用 A 的产物
- **THEN** 可见性判定 MUST 一致地视为可见
- **AND** 若缺失显式依赖导致不可见,错误 MUST 指向可诊断的配置路径并 fail-fast

