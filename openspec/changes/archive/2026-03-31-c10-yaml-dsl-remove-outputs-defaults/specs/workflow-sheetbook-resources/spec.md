## MODIFIED Requirements

### Requirement: legacy sheetbook authoring surface MUST be rejected and migrated to books
系统 MUST 将旧 sheetbook authoring surface 视为已移除,并在 workflow 入口给出可操作迁移路径:

- workflow YAML MUST NOT 接受任何 legacy sheetbook resource group / write intents authoring surface
- 系统 MUST 提示迁移到:
  - `workflow.resources.books.<book_id>.kind=xlsx_memory|xlsx_file`
  - demand outputs 的 `outputs[*].to` / `outputs[*].write` 绑定(显式 `to.book/to.sheet`; SSOT: `yaml-dsl-books-resources`)

#### Scenario: legacy sheetbooks are rejected with migration hint
- **WHEN** workflow YAML 包含任何 legacy sheetbook authoring surface
- **THEN** workflow 校验 MUST fail-fast
- **AND** 错误信息 MUST 包含迁移提示(迁移到 `workflow.resources.books` 与 demand outputs 的 `to/write`)

