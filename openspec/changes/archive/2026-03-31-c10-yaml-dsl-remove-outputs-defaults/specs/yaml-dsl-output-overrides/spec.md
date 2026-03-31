## REMOVED Requirements

### Requirement: by_yaml runtime MUST accept IO-only overrides for `resources.books` and `outputs_defaults`
**原因**：demand YAML 的 `outputs_defaults` 已被破坏性移除,因此运行期不再存在“默认 book 绑定”的 IO-only patch 入口。

**迁移**：

- 若需要改写 output→book 绑定,调用侧应使用 `overrides.outputs`(replace) 显式提供 outputs 列表(含 `to.book`).
- 若仅需改写 book 的 IO 参数(path/budget/export/write_defaults/locks 等),继续使用 `overrides.resources.books`(overlay).

## ADDED Requirements

### Requirement: by_yaml runtime MUST accept IO-only overrides for `resources.books`
系统 MUST 在 `RunOverrides` 中提供 IO-only 覆盖能力,用于在不修改 demand/workflow YAML 的前提下覆盖 books 资源路径/预算/导出配置(仅 IO 层,不触及输出定义层)。

最小集合:

- `overrides.resources`(YAML-shaped patch; 至少支持 `resources.books`)

语义:

- `overrides.resources` MUST 以 patch/overlay 方式应用到 YAML(不做整体 replace)
- 该 patch MUST 仅允许覆盖 IO 层字段(例如 `books.*.path/budget/export_xlsx/write_defaults/allow_formulas/write_lock`),不得覆盖 `outputs[*].fields/where/from/aggregate` 等输出定义层字段

#### Scenario: overriding book path does not require editing YAML
- **GIVEN** demand YAML 声明 `resources.books.report.kind=xlsx_file` 且 `path=./out/report.xlsx`
- **WHEN** 调用方提供 `overrides.resources.books.report.path=./out/report_dev.xlsx`
- **THEN** effective 运行 MUST 将输出写入 `./out/report_dev.xlsx`

### Requirement: by_yaml runtime MUST reject `overrides.outputs_defaults`
系统 MUST 不再接受任何运行期 `outputs_defaults` 覆盖入口:

- `RunOverrides` MUST NOT 暴露 `outputs_defaults` 字段
- 若调用方仍尝试传入 `outputs_defaults`(例如通过旧调用代码),系统 MUST fail-fast(不得静默忽略)

#### Scenario: constructing RunOverrides with outputs_defaults fails fast
- **WHEN** 调用方尝试构造 `RunOverrides(outputs_defaults={\"to\": {\"book\": \"report\"}})`
- **THEN** 构造 MUST 失败(例如抛出 `TypeError`)

