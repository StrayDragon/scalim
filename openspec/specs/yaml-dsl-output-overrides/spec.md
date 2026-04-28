# yaml-dsl-output-overrides Specification

**状态: ✅ 已实现**

## Purpose

为下游”UI 动态选字段/动态输出”场景提供单一标准做法：demand YAML 保持可复用（通常不声明 `outputs`），调用侧在 `run/compile` 时通过 typed `RunOverrides` 显式指定输出编排与 IO 覆盖。

## Related Concepts
- RunOverrides (typed dataclasses)
- outputs 覆盖
- resources/outputs_defaults 覆盖
- 工厂方法
- YAML DSL runtime 模块
## Requirements
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

### Requirement: legacy YAML-shaped overrides inputs MUST be rejected with actionable migration hints

系统 MUST 将以下旧形态视为不再支持的 legacy 输入,并在编译期 fail-fast:

- `RunOverrides.outputs` 为 `list[dict]`
- `RunOverrides.resources` / `RunOverrides.outputs_defaults` 为 `dict`

错误信息 MUST:

- 明确指出 legacy 形态已移除
- 指向稳定逻辑路径(例如 `RunOverrides.outputs`)
- 提供可复制的迁移示例(typed dataclasses / 工厂方法)

#### Scenario: legacy dict overrides fail fast

- **WHEN** 调用方传入 legacy YAML-shaped overrides
- **THEN** 编译 MUST fail-fast
- **AND** 错误信息 MUST 包含迁移提示

### Requirement: `RunOverrides.outputs` MUST take precedence over YAML `outputs`

系统 MUST 将 `RunOverrides.outputs` 视为最高优先级的输出编排来源。

`RunOverrides.outputs` 提供时 MUST 为非空序列; 空序列 MUST fail-fast(避免静默“不导出任何东西”)。

#### Scenario: overrides outputs wins over yaml outputs

- **GIVEN** demand YAML 声明了 `outputs` 且包含字段列表 `["a"]`
- **WHEN** 调用方提供 `RunOverrides.outputs` 且包含字段列表 `["b"]`
- **THEN** effective outputs MUST 使用 `["b"]` 而不是 `["a"]`

### Requirement: `RunOverrides.outputs` MUST compile through the same outputs pipeline

系统 MUST 使用与 YAML `outputs` 相同的解析/校验/编译链路来处理 `RunOverrides.outputs`,以避免维护两套输出语义并保证错误信息一致性。

#### Scenario: invalid typed overrides outputs fails fast with a diagnosable error

- **WHEN** 调用方提供的 typed `RunOverrides.outputs` 结构非法(例如缺少 `name/fields`,或 `to` 互斥关系非法)
- **THEN** 编译 MUST fail-fast
- **AND** 错误信息 MUST 指向可定位的逻辑路径(例如 `RunOverrides.outputs[0].name`)

### Requirement: YAML DSL runtime MUST accept typed `RunOverrides.outputs` (dataclasses)

系统 MUST 在 YAML DSL runtime 的 `RunOverrides` 中提供 `outputs` 覆盖字段,用于在不修改 demand YAML 的前提下运行期指定输出编排。

与旧的 YAML-shaped `list[dict]` 不同，`RunOverrides.outputs` MUST 为 typed dataclasses 序列，并且 MUST 可从 YAML DSL runtime 模块稳定导入。

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

### Requirement: demand compile and workflow compile MUST share the same overrides compilation pipeline

系统 MUST 仅保留一套 overrides 解析/校验实现(SSOT),并同时服务于:
- 单 demand runtime compile (`compile/run`)
- workflow compile (`compile_workflow` 等)

系统 MUST NOT 维护两份“语义等价但实现不同”的 overrides parser/validator,以避免规则漂移与修复遗漏。

#### Scenario: override validation behavior stays consistent across entrypoints
- **GIVEN** 某个非法的 `RunOverrides.outputs`(例如 to.file 与 to.book/to.sheet 互斥冲突)
- **WHEN** 调用方分别在 demand compile 与 workflow compile 路径触发该校验
- **THEN** 两条路径 MUST 都 fail-fast
- **AND** 报错类型 MUST 一致

### Requirement: invalid overrides MUST raise ScalimWorkflowConfigError with stable path

当 overrides/resources/outputs_defaults/output_extras 的输入非法时,系统 MUST 抛出 `ScalimWorkflowConfigError` 并提供稳定可定位的 `path=`。

#### Scenario: invalid typed overrides fails with ScalimWorkflowConfigError
- **WHEN** 调用方提供非法的 typed overrides
- **THEN** 系统 MUST 抛 `ScalimWorkflowConfigError`
- **AND** `path` MUST 指向可定位的逻辑路径(例如 `overrides.outputs.0.to` 或 `overrides.outputs_defaults.to.book`)

