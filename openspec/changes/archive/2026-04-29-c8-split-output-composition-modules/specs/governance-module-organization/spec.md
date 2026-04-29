## ADDED Requirements

### Requirement: output_composition hotspot MUST be decomposed into spec/router/builder submodules

系统 MUST 将 `execution/output_composition.py` 这类混合 spec+runtime+builder 的热点模块拆分为职责单一的子模块,至少分离:
- spec/数据类层
- router/runtime 实现层
- builder/工厂层

拆分后系统 MUST 保持:
- `scalim.execution.output_composition` 的稳定导入路径继续可用
- 对外行为不变(纯重构)

#### Scenario: stable import path remains after refactor
- **WHEN** 维护者将 output composition 代码迁移到子模块/子包
- **THEN** 调用方仍可通过 `scalim.execution.output_composition` 导入公共类型与 `build_output_composition`
- **AND** `just qa` MUST 通过
