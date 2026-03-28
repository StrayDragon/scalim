## MODIFIED Requirements

### Requirement: schema 覆盖 `outputs.*.container.path` 的 `{$init_var: <name>}` 语法

系统 MUST 在 YAML DSL JSON Schema 中继续支持 `outputs[*].container.path` 使用 `{$init_var: <name>}` 指令节点注入输出路径,但该能力仅作为 **CSV 文件输出** 的最小子集保留:

- 仅当 `outputs[*].container.type: csv` 时允许
- `outputs[*].container.path` MUST 支持:
  - 非空静态字符串路径
  - 或 `{$init_var: <name>}` 指令节点(对象节点,不是字符串插值)
- `outputs[*].container.path: \"\"`(空字符串) MUST 被拒绝(见本变更对 pathless CSV 的移除)

说明:

- `.xlsx` 输出路径注入 MUST 迁移为 `resources.books.*.path` / `export_xlsx.path`(见本变更新增 requirements)。

#### Scenario: schema validate accepts string or init_var object for csv output paths
- **WHEN** 执行 demand schema-only 校验且 `outputs[0].container.type=csv` 且 `outputs[0].container.path={$init_var: output_path}`
- **THEN** 校验 MUST 通过

## REMOVED Requirements

### Requirement: schema MAY allow pathless CSV outputs for workflow-managed temp outputs
**原因**：pathless CSV (`container.type: csv` + `path: ""`) 是实现细节泄露,已被本变更破坏性移除。

**迁移**：使用 `resources.books` + `outputs_defaults.to.book`/`outputs[*].to` 表达输出契约；workflow-managed 中间态由实现自动选择,不再通过空路径触发。

## ADDED Requirements

### Requirement: schema MUST support `{$init_var: <name>}` for book export paths
系统 MUST 在 YAML DSL JSON Schema 中对以下路径字段支持 `{$init_var: <name>}` 指令节点(对象节点,不是字符串插值):

- demand: `resources.books.*.path` (当 `kind=xlsx_file`)
- demand/workflow: `*.resources.books.*.export_xlsx.path` (当 `kind=xlsx_memory` 且启用导出)

其中 `{$init_var: <name>}` 在 schema 层的结构 MUST 满足:

- YAML 值为 object(mapping)
- object MUST 仅包含 key `"$init_var"`
- `"$init_var"` 的 value MUST 为非空字符串
- object MUST `additionalProperties=false`

#### Scenario: schema validate accepts string or init_var object for book paths
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json` 与 `workflow.gen.json`
- **THEN** book 的 `path`/`export_xlsx.path` 字段 MUST 通过 `oneOf` 接受 string 或 `{$init_var: <name>}` object

### Requirement: demand schema MUST reject legacy output container types and shapes (`workbook`, pathless `csv`)

系统 MUST 在 demand schema-only 校验阶段拒绝以下已移除/不再作为主路径的形态:

- `outputs[*].container.type: workbook`
- `outputs[*].container.type: csv` 且 `outputs[*].container.path: ""`

#### Scenario: workbook container type is rejected by schema
- **WHEN** 执行 demand schema-only 校验且 `outputs[0].container.type=workbook`
- **THEN** 校验 MUST 失败

#### Scenario: pathless csv is rejected by schema
- **WHEN** 执行 demand schema-only 校验且 `outputs[0].container.type=csv` 且 `outputs[0].container.path=\"\"`
- **THEN** 校验 MUST 失败

### Requirement: workflow schema MUST reject legacy workflow IO fields (`writes`, `workbooks`, `csvs`, `sheetbooks`)

系统 MUST 在 workflow JSON schema 中拒绝已移除的 workflow IO authoring surface:

- `workflow.runs[*].writes`
- `workflow.resources.workbooks`
- `workflow.resources.csvs`
- `workflow.resources.sheetbooks`

并要求 workflow 的共享 IO 统一通过:

- `workflow.resources.books`

#### Scenario: workflow schema rejects removed `writes`
- **WHEN** 执行 workflow schema-only 校验且出现 `workflow.runs[0].writes`
- **THEN** 校验 MUST 失败

#### Scenario: workflow schema rejects legacy resources
- **WHEN** 执行 workflow schema-only 校验且出现 `workflow.resources.sheetbooks`
- **THEN** 校验 MUST 失败
