# workflow-sheetbook-resources Specification

**状态: ✅ 已实现**

## Purpose
定义 workflow YAML 的共享 `.xlsx` book 资源(以 `workflow.resources.books` 表达)的迁移约束与运行期契约: 预算护栏、确定性写入、冲突安全、可观测且可原子导出为最终 xlsx,并提供可稳定引用的内置 loader 供下游节点读取 sheet rows.
## Requirements
### Requirement: legacy sheetbook authoring surface MUST be rejected and migrated to books
系统 MUST 将旧 sheetbook authoring surface 视为已移除,并在 workflow 入口给出可操作迁移路径:

- workflow YAML MUST NOT 接受任何 legacy sheetbook resource group / write intents authoring surface
- 系统 MUST 提示迁移到:
  - `workflow.resources.books.<book_id>.kind=xlsx_memory|xlsx_file`
  - demand outputs 的 `outputs_defaults.to`/`outputs[*].to`/`outputs[*].write` 绑定(SSOT: `yaml-dsl-books-resources`)

#### Scenario: legacy sheetbooks are rejected with migration hint
- **WHEN** workflow YAML 包含任何 legacy sheetbook authoring surface
- **THEN** workflow 校验 MUST fail-fast
- **AND** 错误信息 MUST 包含迁移提示(迁移到 `workflow.resources.books` 与 demand outputs 的 `to/write`)
