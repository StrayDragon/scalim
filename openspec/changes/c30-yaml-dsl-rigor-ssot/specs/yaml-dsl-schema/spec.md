## ADDED Requirements

### Requirement: enums and defaults MUST be sourced from schema_dsl SSOT

系统 MUST 将 YAML DSL 的枚举/默认值/描述文本收敛到 schema_dsl 作为单点 SSOT.

约束:
- runtime validator/parser MUST 引用 schema_dsl 的导出,不得复制同一份枚举/默认值常量
- 系统 MUST 提供一致性自检（测试或脚本），确保 schema 接受的枚举与 runtime 接受的枚举一致

#### Scenario: enum drift is detected
- **WHEN** 维护者修改 schema_dsl 中某个 enum/默认值
- **AND** runtime validator/parser 未同步（出现不一致）
- **THEN** 一致性自检 MUST fail-fast 并指出不一致字段

