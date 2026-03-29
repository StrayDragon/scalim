## REMOVED Requirements

### Requirement: default vocabulary MUST include workflow sheetbook loader id
**Reason**：sheetbook 术语与 authoring surface 已收敛到 `books.kind=xlsx_memory`；默认 vocabulary 中不应继续暴露 `sheetbook_*` 命名。

**Migration**：使用 `^workflow/book_sheet_rows`(见本变更对 `yaml-dsl-books-resources` 的定义)。

## ADDED Requirements

### Requirement: default vocabulary MUST include workflow book sheet rows loader id
系统 MUST 至少提供一个可用的内置 callable id,用于 workflow 场景的内置 loader:

- `^workflow/book_sheet_rows` → workflow book sheet rows loader (`scalim.workflow.loaders:book_sheet_rows`)

#### Scenario: workflow book sheet rows loader id is available
- **WHEN** 调用方在 YAML 中声明 `loader: ^workflow/book_sheet_rows`
- **THEN** 解析与运行期 callable 解析 MUST 成功

