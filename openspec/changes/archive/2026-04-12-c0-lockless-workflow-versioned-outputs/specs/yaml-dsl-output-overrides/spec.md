# yaml-dsl-output-overrides Specification

## MODIFIED Requirements

### Requirement: `RunOverrides` MUST provide factory methods for the common “single-sheet dynamic fields export” scenario

系统 MUST 在 `RunOverrides` 上提供标准 `@classmethod` 工厂方法,以覆盖最常见的下游集成场景:

- 单表
- 单 sheet
- 字段动态(由调用方指定 field_id 列表)
- 输出 root 动态(由调用方指定输出 root 目录;版本化输出 D-2)

该工厂方法 MUST:

- 只构造 detail output 的最小子集
- 同时覆盖 `resources.*` 与 `outputs_defaults` 的必要拼装,避免调用方重复拼结构

#### Scenario: factory builds a runnable overrides bundle

- **WHEN** 调用方使用 `RunOverrides.<factory>(output_root=..., fields=[...], sheet=...)`
- **THEN** 返回的 overrides MUST 可直接用于 `run/compile` 并产生预期输出

### Requirement: YAML DSL runtime MUST accept IO-only overrides for `resources` and `outputs_defaults`

系统 MUST 在 `RunOverrides` 中提供 IO-only 覆盖能力,用于在不修改 demand/workflow YAML 的前提下,覆盖 resources 与默认输出绑定(仅 IO 层,不触及输出定义层)。

最小集合:

- `RunOverrides.resources`(typed dataclasses;至少支持 `resources.books` 与 `resources.files`)
- `RunOverrides.outputs_defaults`(typed dataclasses;至少支持 `outputs_defaults.to.book`)

语义:

- `RunOverrides.resources` 与 `RunOverrides.outputs_defaults` MUST 以 patch/overlay 方式应用到 YAML(不做整体 replace)
- overlay MUST 仅允许覆盖 IO 层字段(例如 `books.*.path/budget/export_xlsx/write_defaults/allow_formulas` 或 `files.*.path/encoding`)
- overlay MUST NOT 允许覆盖输出定义层字段(例如 `outputs[*].where/from/aggregate`)

#### Scenario: overriding book output root does not require editing YAML

- **GIVEN** demand YAML 声明 `resources.books.report.kind=xlsx_file` 且 `path=./out`
- **WHEN** 调用方提供 `RunOverrides.resources.books["report"].path=./out_dev`
- **THEN** effective 运行 MUST 将产物发布到 `./out_dev/versions/<version_id>/books/report.xlsx`

#### Scenario: overriding file encoding does not require editing YAML

- **GIVEN** demand/workflow YAML 声明 `resources.files.detail.kind=csv_file` 且未显式设置 `encoding`
- **WHEN** 调用方提供 `RunOverrides.resources.files["detail"].encoding=utf-16`
- **THEN** effective file resource config MUST 使 `resources.files.detail.encoding` 等价为 `utf-16`
