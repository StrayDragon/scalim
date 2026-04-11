# yaml-dsl-output-overrides (delta) Specification

## MODIFIED Requirements

### Requirement: YAML DSL runtime MUST accept IO-only overrides for `resources` and `outputs_defaults`

系统 MUST 在 `RunOverrides` 中提供 IO-only 覆盖能力,用于在不修改 demand/workflow YAML 的前提下,覆盖 resources 与默认输出绑定(仅 IO 层,不触及输出定义层)。

最小集合:

- `RunOverrides.resources`(typed dataclasses;至少支持 `resources.books` 与 `resources.files`)
- `RunOverrides.outputs_defaults`(typed dataclasses;至少支持 `outputs_defaults.to.book`)

语义:

- `RunOverrides.resources` 与 `RunOverrides.outputs_defaults` MUST 以 patch/overlay 方式应用到 YAML(不做整体 replace)
- overlay MUST 仅允许覆盖 IO 层字段(例如 `books.*.path/budget/export_xlsx/write_defaults/allow_formulas/write_lock` 或 `files.*.path/encoding/write_lock`)
- overlay MUST NOT 允许覆盖输出定义层字段(例如 `outputs[*].where/from/aggregate`)

#### Scenario: overriding book path does not require editing YAML

- **GIVEN** demand YAML 声明 `resources.books.report.kind=xlsx_file` 且 `path=./out/report.xlsx`
- **WHEN** 调用方提供 `RunOverrides.resources.books["report"].path=./out/report_dev.xlsx`
- **THEN** effective 运行 MUST 将输出写入 `./out/report_dev.xlsx`

#### Scenario: overriding file write_lock does not require editing YAML

- **GIVEN** demand/workflow YAML 声明 `resources.files.detail.kind=csv_file` 且 `path=./out/detail.csv`
- **WHEN** 调用方提供 `RunOverrides.resources.files["detail"].write_lock=true`
- **THEN** effective file resource config MUST 使 `resources.files.detail.write_lock` 等价为 `true`
