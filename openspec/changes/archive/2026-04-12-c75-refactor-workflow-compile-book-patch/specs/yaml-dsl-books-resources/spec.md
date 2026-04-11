# yaml-dsl-books-resources (delta) Specification

## ADDED Requirements

### Requirement: workflow book patches MUST be applied with strict contracts and consistent diagnostics

当 workflow compile 对 `workflow.resources.books.<book_id>`（以及其嵌套字段如 `write_defaults` / `budget` / `export_xlsx`）应用 patch/overlay 时，系统 MUST 提供严格且可预测的契约校验：

- 对任意 patch mapping，系统 MUST 检测 unknown keys 并 fail-fast
- 对任意字段类型不匹配（例如期望 bool 但得到 list），系统 MUST fail-fast 且诊断信息 MUST 指向准确逻辑 path
- 对 `write_defaults` 等枚举字段，系统 MUST 以一致口径校验并提供可行动错误提示
- 上述校验 SHOULD 由集中实现的 helper 承载，避免同类规则在不同入口漂移

#### Scenario: unknown book patch key fails fast with a precise path
- **GIVEN** 用户在 `workflow.resources.books.report` 中提供未知字段 `unknown_key`
- **WHEN** workflow compile 应用 book patch
- **THEN** 系统 MUST fail-fast
- **AND** 错误诊断 MUST 指向 `workflow.resources.books.report.unknown_key`

#### Scenario: nested write_defaults enum validation is consistent
- **GIVEN** 用户提供 `write_defaults.on_mismatch=not_a_policy`
- **WHEN** workflow compile 校验该配置
- **THEN** 系统 MUST fail-fast
- **AND** 错误 MUST 提示允许值集合（`error|warn|skip`）

