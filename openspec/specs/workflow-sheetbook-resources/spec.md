# workflow-sheetbook-resources Specification

**状态: ✅ 已实现**

## Purpose
定义 workflow YAML 的 sheetbook 资源(authoring surface)、预算护栏与写入 intent(`writes[*].sheetbook_*`)契约,并要求写入行为确定性、冲突安全、可观测且可原子导出为最终 xlsx,同时提供内置 loader 供下游节点读取 sheet rows.
## Requirements
### Requirement: legacy sheetbook authoring surface MUST be rejected and migrated to books
系统 MUST 将旧 sheetbook authoring surface 视为已移除,并在 workflow 入口给出可操作迁移路径:

- workflow YAML MUST NOT 接受 `workflow.resources.sheetbooks`
- workflow YAML MUST NOT 接受 `workflow.runs[*].writes[*].sheetbook_*` intents
- 系统 MUST 提示迁移到:
  - `workflow.resources.books.<book_id>.kind=xlsx_memory|xlsx_file`
  - demand outputs 的 `outputs_defaults.to`/`outputs[*].to`/`outputs[*].write` 绑定(SSOT: `yaml-dsl-books-resources`)

#### Scenario: legacy sheetbooks are rejected with migration hint
- **WHEN** workflow YAML 包含 `workflow.resources.sheetbooks` 或 `workflow.runs[*].writes[*].sheetbook_*`
- **THEN** workflow 校验 MUST fail-fast
- **AND** 错误信息 MUST 包含迁移提示(迁移到 `workflow.resources.books` 与 demand outputs 的 `to/write`)

