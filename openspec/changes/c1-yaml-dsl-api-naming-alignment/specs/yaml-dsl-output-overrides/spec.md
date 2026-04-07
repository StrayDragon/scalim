## MODIFIED Requirements

### Requirement: by_yaml runtime MUST accept typed `RunOverrides.outputs` (dataclasses)

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
