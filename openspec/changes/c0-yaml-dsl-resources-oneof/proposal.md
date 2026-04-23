## Why

YAML DSL 的大多数“分支对象”已经采用 `{<variant>: {...}}` 的 oneOf 分支写法（如 `sources.*.normalize`、aggregate producers），但 `resources.books.*` 与 `resources.files.*` 仍使用 `kind: <variant>` discriminator，导致 authoring 风格不一致、可读性与可组合性偏差，并让 schema/validator 需要额外的 kind-based if/then 与 fail-fast 分支逻辑。

当前 books/files 资源面已稳定（作为对外统一术语），且 demand 侧需要与 `$import` 复用机制良好协作，因此适合将资源声明升级为 oneOf 分支写法并在 demand/workflow 两侧对齐。

## What Changes

- **BREAKING**：在 demand 与 workflow YAML 中，将 `resources.books.<book_id>` 从 `{kind: xlsx_file|xlsx_memory, ...}` 升级为 oneOf 分支对象 `{xlsx_file: {...}} | {xlsx_memory: {...}}`。
- **BREAKING**：在 demand 与 workflow YAML 中，将 `resources.files.<file_id>` 从 `{kind: csv_file, ...}` 升级为 `{csv_file: {...}}`（并将 `encoding` 收敛到 `resources.files.<id>.csv_file.encoding`；默认仍为 `utf-8`）。
- 保持并明确“跨分支公共字段”与分支并存的写法：
  - `resources.books.<book_id>.write_defaults` 仍作为公共字段与 `xlsx_file/xlsx_memory` 分支并存（与 `sources.*.normalize.call_by` 模式一致）。
- demand 的 `$import` 继续可用于 `resources.*` 片段复用（**节点级/分支级**），且允许与本地 override 并存（导入值作为 defaults，本地覆盖导入值）；workflow 仍不支持 imports expansion：
  - demand schema 显式允许 `{ $import: ... }` 作为资源节点/资源分支形态（编辑器 schema-only 校验不展开 import）。
  - workflow schema/parse 继续 fail-fast 拒绝 `$import`（并提供迁移提示）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-dsl-books-resources`: 资源声明从 kind discriminator 迁移到 oneOf 分支写法，并更新 schema-only 校验示例与约束路径（`path/budget/export_xlsx/allow_formulas/write_defaults` 的归属与诊断）。
- `yaml-dsl-file-resources`: 资源声明从 `kind=csv_file` 迁移到 `{csv_file: ...}`，并更新 schema-only 校验示例与路径语义。

## Impact

- Schema SSOT:
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py`（books/files schema shape + oneOf 分支）
  - 生成物: `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`, `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`（生成入口：`just gen-yaml-dsl-schema`；禁止手工编辑）
- 解析/校验:
  - demand loader/validator: `src/scalim/dsl/yaml_dsl/_internal/config_parsing/loader.py`, `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py`
  - workflow parser: `src/scalim/dsl/yaml_dsl/workflow_config/_parse.py`
- 文档/示例(按需):
  - `docs/doc/yaml-dsl/user-guide.md`
  - `agentdev/skills/scalim-yaml-dsl/references/**`
