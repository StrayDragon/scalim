## ADDED Requirements

### Requirement: YAML DSL manual pages MUST not present removed syntax and MUST reflect current imports/outputs surfaces
系统 MUST 确保文档站点(`docs/doc/`)中的 YAML DSL 手册页与实现保持一致,避免“按文档写 YAML 但 validate/compile 失败”的漂移。

至少 MUST 覆盖以下手册页:

- `docs/doc/yaml-dsl/syntax.md`
- `docs/doc/yaml-dsl/capability-matrix.md`
- `docs/doc/yaml-dsl/user-guide.md`

并且手册页 MUST 满足:

- 不得把已移除的 `outputs.*.container.type: workbook` 作为可用示例或推荐写法
- 必须将 `outputs.*.container` 明确为 CSV 文件输出 authoring surface
- 必须将 Excel 输出 authoring surface 指向 `resources.books` + `outputs.*.to`
- imports/$import 的路径解析与限制描述不得与当前实现/规范冲突(例如错误地声称“仅同级文件”)

#### Scenario: docs do not recommend workbook container
- **WHEN** 读者按 `docs/doc/yaml-dsl/user-guide.md` 的 outputs 示例编写 YAML
- **THEN** 该示例不得包含 `container.type: workbook`

#### Scenario: docs describe csv-only container surface and books binding for xlsx
- **WHEN** 读者查看 outputs 相关章节
- **THEN** 文档 MUST 描述 `outputs.*.container` 为 CSV-only
- **AND** 文档 MUST 描述 Excel 输出通过 `resources.books` + `outputs.*.to` 绑定实现

