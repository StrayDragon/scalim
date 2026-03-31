## MODIFIED Requirements

### Requirement: by_yaml runtime MUST accept YAML-shaped `overrides.outputs` with the unified target surface
系统 MUST 在 by_yaml runtime 的 `RunOverrides.outputs` 中接受与 YAML authoring surface 同形的统一输出结构,用于在不修改 YAML 的前提下运行期指定输出编排。

`overrides.outputs[*]` 的最小承诺子集 MUST 至少包含:

- `name`
- `to` (`to.file` 或 `to.book` / `to.sheet`)
- `write`
- `fields`

约束:

- `overrides.outputs[*]` MUST NOT 接受 `container`
- `overrides.outputs[*].to` MUST 与 YAML `outputs[*].to` 共享相同语义与校验规则
- `overrides.outputs[*].write` MUST 与 YAML `outputs[*].write` 共享相同语义与校验规则

#### Scenario: overrides provides a csv output through to.file
- **GIVEN** demand YAML 未声明 `outputs`
- **WHEN** 调用方提供 `overrides.outputs` 且其中某个 output 使用 `to.file`
- **THEN** 本次运行 MUST 使用该 output 作为 effective output

#### Scenario: overrides rejects legacy container
- **WHEN** 调用方在 `overrides.outputs[*]` 中声明 `container`
- **THEN** 编译 MUST fail-fast
- **AND** 错误信息 MUST 指向 `overrides.outputs[*].container`

### Requirement: by_yaml runtime MUST accept IO-only overrides for `resources.books` and `resources.files`
系统 MUST 在 `RunOverrides.resources` 中提供对统一资源面的 IO-only patch 能力:

- `overrides.resources.books`
- `overrides.resources.files`

语义:

- patch MUST 以 overlay 方式应用到 effective resources
- patch MUST 仅允许覆盖 IO 层字段,不得改写 `outputs[*].fields/where/from/aggregate`

#### Scenario: overriding file path does not require editing YAML
- **GIVEN** demand YAML 声明 `resources.files.detail.kind=csv_file`
- **AND** `resources.files.detail.path=./out/a.csv`
- **WHEN** 调用方提供 `overrides.resources.files.detail.path=./out/b.csv`
- **THEN** effective 运行 MUST 将输出写入 `./out/b.csv`
