## MODIFIED Requirements

### Requirement: 多输出组合 MUST compile from a unified destination-binding model
系统 SHALL 从统一的 output target model 编译多输出组合,而不是区分 `container` 与 `books` 两套入口。

统一模型至少包含:

- destination binding: `to.file` 或 `to.book`
- write policy: `write.*`
- layout fields: `fields`

约束:

- CSV `OutputSpec` MUST 由 `resources.files + to.file + write` 推导
- Excel `OutputSpec` MUST 由 `resources.books + to.book + to.sheet + write` 推导
- 编译链路 MUST NOT 再依赖 `outputs[*].container`

#### Scenario: file and book outputs compile through the same target normalization pipeline
- **WHEN** 一次运行同时包含 `to.file` 与 `to.book` 两类 outputs
- **THEN** 系统 MUST 先将它们归一化为统一 target model
- **AND** 再生成对应的 CSV / Excel 输出规范

### Requirement: effective header-name validation MUST follow unified write semantics
系统 MUST 在输出编译阶段按统一 `write` 语义判断是否需要启用“有效显示名唯一”校验。

#### Scenario: duplicate display names are rejected for file outputs using named headers
- **GIVEN** 某 file output 会输出表头
- **AND** `write.header_fields_output_by=name`
- **WHEN** 两个字段的 effective display name 相同
- **THEN** 编译 MUST fail-fast

#### Scenario: duplicate display names are rejected for book outputs using named headers
- **GIVEN** 某 books output 会输出表头
- **AND** `write.header_fields_output_by=name`
- **WHEN** 两个字段的 effective display name 相同
- **THEN** 编译 MUST fail-fast
