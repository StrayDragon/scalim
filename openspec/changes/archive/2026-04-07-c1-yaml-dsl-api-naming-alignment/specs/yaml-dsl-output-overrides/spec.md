## REMOVED Requirements

### Requirement: by_yaml runtime MUST accept typed `RunOverrides.outputs` (dataclasses)
**Reason**：YAML DSL 的 canonical public facade 已从 `scalim.dsl.by_yaml` 收敛为 `scalim.dsl.yaml_dsl`；对外契约与文档应不再以 `by_yaml` 命名描述 runtime 边界。

### Requirement: by_yaml runtime MUST accept IO-only overrides for `resources` and `outputs_defaults`
**Reason**：同上；旧的 `by_yaml` 命名不再作为用户侧稳定契约保留。

## ADDED Requirements

### Requirement: YAML DSL runtime MUST accept typed `RunOverrides.outputs` (dataclasses)

系统 MUST 在 YAML DSL runtime 的 `RunOverrides` 中提供 `outputs` 覆盖字段,用于在不修改 demand YAML 的前提下运行期指定输出编排。

与旧的 YAML-shaped `list[dict]` 不同,`RunOverrides.outputs` MUST 为 typed dataclasses 序列,并且 MUST 可从 `scalim.dsl.yaml_dsl` 稳定导入。

本 spec 仅承诺明细输出(detail)的最小子集,至少包含:

- `name`
- `fields`(有序 field_id list)
- `to`(book/sheet 绑定) 或 `to.file`(csv 文件输出) 二选一
- `write`(可选;仅在 book 绑定输出时允许)

`RunOverrides.outputs[*]` MUST NOT 支持以下 keys/语义(未来如需支持应另开 change 增量扩展):

- `where`
- `from`
- `aggregate`

#### Scenario: overrides provides a single book output

- **GIVEN** demand YAML 未声明 `outputs`
- **WHEN** 调用方在 `run/compile` 中提供 `RunOverrides(outputs=(OutputOverride(...),))`,且该 output 包含 `to.sheet` 与 `fields`
- **THEN** 本次运行 MUST 以该 `RunOverrides.outputs` 作为 effective outputs
- **AND** 导出字段顺序 MUST 与 `fields` 一致

#### Scenario: overrides provides a single csv output

- **GIVEN** demand YAML 未声明 `outputs`
- **WHEN** 调用方在 `run/compile` 中提供 `RunOverrides.outputs` 且该 output 使用 `to.file` 与 `fields`
- **THEN** 本次运行 MUST 写出 CSV 输出

### Requirement: YAML DSL runtime MUST accept IO-only overrides for `resources` and `outputs_defaults`

系统 MUST 在 `RunOverrides` 中提供 IO-only 覆盖能力,用于在不修改 demand/workflow YAML 的前提下,覆盖 resources 与默认输出绑定(仅 IO 层,不触及输出定义层)。

最小集合:

- `RunOverrides.resources`(typed dataclasses;至少支持 `resources.books` 与 `resources.files`)
- `RunOverrides.outputs_defaults`(typed dataclasses;至少支持 `outputs_defaults.to.book`)

语义:

- `RunOverrides.resources` 与 `RunOverrides.outputs_defaults` MUST 以 patch/overlay 方式应用到 YAML(不做整体 replace)
- overlay MUST 仅允许覆盖 IO 层字段(例如 `books.*.path/budget/export_xlsx/write_defaults/allow_formulas/write_lock` 或 `files.*.path/encoding`)
- overlay MUST NOT 允许覆盖输出定义层字段(例如 `outputs[*].where/from/aggregate`)

#### Scenario: overriding book path does not require editing YAML

- **GIVEN** demand YAML 声明 `resources.books.report.kind=xlsx_file` 且 `path=./out/report.xlsx`
- **WHEN** 调用方提供 `RunOverrides.resources.books["report"].path=./out/report_dev.xlsx`
- **THEN** effective 运行 MUST 将输出写入 `./out/report_dev.xlsx`
