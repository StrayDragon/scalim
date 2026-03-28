## REMOVED Requirements

### Requirement: workflow YAML exposes a stable authoring surface for sheetbooks
**Reason**：用户侧 sheetbook/workbook 概念割裂已被统一为 `resources.books` + `kind=xlsx_memory|xlsx_file`；workflow YAML 不再暴露 `workflow.resources.sheetbooks` 与 `writes[*].sheetbook_*` authoring surface。

**Migration**：使用 `workflow.resources.books.<id>.kind=xlsx_memory` + demand outputs 的 `to.book/to.sheet` 绑定。

### Requirement: workflow MUST support in-memory sheetbook resources
**Reason**：该能力仍需要,但用户侧术语与入口已收敛为 `books.kind=xlsx_memory`。

**Migration**：改用 `resources.books.<id>.kind=xlsx_memory` 并遵循 `yaml-dsl-books-resources` 的 budget/export_xlsx 约束。

### Requirement: writes to a sheetbook MUST be deterministic and conflict-safe
**Reason**：写入确定性与冲突策略仍需要,但写入意图已从 workflow `writes` 收敛为 demand outputs 的 `write_defaults`/`outputs[*].write`。

**Migration**：使用 `resources.books.*.write_defaults` 与 `outputs[*].write` 表达 append/sheet 语义；确定性顺序由 `runs` 顺序 + `outputs` 顺序决定(见 `workflow-shared-output-containers`)。

### Requirement: workflow MUST support exporting a sheetbook to an Excel workbook atomically
**Reason**：导出能力仍需要,但入口已收敛为 `books.kind=xlsx_memory.export_xlsx`。

**Migration**：使用 `workflow.resources.books.<id>.kind=xlsx_memory` + `export_xlsx.path`(可选)。

### Requirement: demand nodes MUST be able to consume sheetbook sheet rows via a built-in loader
**Reason**：读取能力仍需要,但 loader 与内置 callable id 已随 book 统一重命名。

**Migration**：使用 `scalim.workflow.loaders:book_sheet_rows` 或 `^workflow/book_sheet_rows`(见 `yaml-dsl-books-resources` 与 `yaml-dsl-builtin-callables`)。

### Requirement: workflow MUST precheck Excel output-path collisions across nodes
**Reason**：该预检查能力仍需要,但其 SSOT 已迁移到 book 导出路径(而非 sheetbook/workbook 旧资源组)。

**Migration**：使用 `workflow.resources.books` 的 effective `path`/`export_xlsx.path` 作为冲突检查对象(见 `workflow-shared-output-containers`)。

### Requirement: sheetbook lifecycle MUST be observable and joinable
**Reason**：可观测性仍需要,但资源类型名称已收敛为 book。

**Migration**：保持 `workflow_resource_*` 事件,其 `resource_type`/归因字段按 book 统一。

### Requirement: sheetbook plan creation MUST be atomic within a workflow exec
**Reason**：并发下 get-or-create 原子性仍需要,但资源类型名称已收敛为 book。

**Migration**：同一 workflow exec 内对同一 book 的 plan 创建 MUST 原子(见 `workflow-shared-output-containers`)。

### Requirement: sheetbook xlsx export MUST escape Excel formulas by default
**Reason**：公式转义仍需要,但出口已收敛为 book 导出语义。

**Migration**：使用 `books.*.allow_formulas` / `books.*.export_xlsx.allow_formulas` 控制转义(见 `yaml-dsl-books-resources`)。

### Requirement: sheetbook export_xlsx authoring surface MUST support allow_formulas
**Reason**：allow_formulas 仍需要,但 authoring surface 已收敛到 `resources.books.*`。

**Migration**：改用 `workflow.resources.books.<id>.export_xlsx.allow_formulas`。

