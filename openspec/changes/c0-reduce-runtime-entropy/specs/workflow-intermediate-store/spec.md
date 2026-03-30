## ADDED Requirements

### Requirement: workflow typed rows artifact MUST have a stable public import path
系统 MUST 为 workflow typed rows artifact `InMemoryRows` 提供稳定的公开导入路径,并避免跨层绑定内部实现模块路径。

约束:
- `InMemoryRows` MUST 可从稳定 facade 导入(例如 `IMPL_ROOT.sinks` 或等价稳定入口)。
- workflow runtime 与 execution orchestration MUST NOT 直接依赖 `IMPL_ROOT.sinks._internal.*` 路径获取该类型(内部路径可变,非契约)。

#### Scenario: InMemoryRows is importable from a stable facade module
- **WHEN** 调用方导入 `InMemoryRows` 的稳定公开入口
- **THEN** 导入 MUST 成功且类型与 runtime 实际使用的 typed rows artifact 一致

