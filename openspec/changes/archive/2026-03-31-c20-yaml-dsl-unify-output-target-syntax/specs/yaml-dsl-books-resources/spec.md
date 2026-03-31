## MODIFIED Requirements

### Requirement: `.xlsx` outputs MUST use books binding and all outputs MUST use the unified `to/write` authoring surface (BREAKING)
系统 MUST 将输出 authoring surface 收敛到 `resources + outputs[*].to + outputs[*].write`,并移除 `outputs[*].container` 这条并行路径。

约束:

- `.xlsx` 输出 MUST 使用 `resources.books` + `outputs[*].to.book`
- CSV 输出 MUST 使用 `resources.files` + `outputs[*].to.file`
- `outputs[*].container` MUST 在 schema-only 与 runtime semantic 校验阶段被拒绝
- `outputs[*].to` MUST 成为唯一目标绑定入口
- `outputs[*].write` MUST 成为唯一写入策略入口

#### Scenario: legacy container output is rejected with migration hint
- **WHEN** demand YAML 仍声明 `outputs[*].container`
- **THEN** schema-only 与 runtime 校验 MUST fail-fast
- **AND** 错误信息 MUST 提示迁移到 `resources.files/resources.books` + `outputs[*].to` + `outputs[*].write`

### Requirement: demand MUST bind books through `outputs[*].to.book` and use `outputs[*].write` for output-local write behavior
系统 MUST 支持在 demand YAML 中通过 output-local 结构绑定 books:

- `outputs[*].to.book` MUST 为非空字符串
- `outputs[*].to.sheet` MAY 为非空字符串
- `outputs[*].write.header_fields_output_by` MAY 存在,默认 `name`
- `outputs[*].write.include_header` MAY 存在; 当 effective `mode=append` 时 MUST NOT 显式声明
- `resources.books.<id>.write_defaults` 仅允许 book 专属字段,不得承载 `header_fields_output_by/include_header`

#### Scenario: books output can override header source at output-local write
- **WHEN** output 声明 `to.book=report`
- **AND** `write.header_fields_output_by=field_id`
- **THEN** 该 output 的表头来源 MUST 使用 `field_id`

#### Scenario: include_header is rejected for append-mode books output
- **GIVEN** output 绑定到某个 book
- **AND** effective `mode=append`
- **WHEN** 用户显式声明 `write.include_header`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示 `append` 模式应使用 `header_policy`
