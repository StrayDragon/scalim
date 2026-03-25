# yaml-dsl-output-overrides Specification

**状态: ✅ 已实现**
## Purpose
为下游“UI 动态选字段/动态输出”场景提供单一标准做法: demand YAML 保持可复用(通常不声明 `outputs`),调用侧在 `run/compile` 时通过与 YAML 同形的 `overrides.outputs` 显式指定输出。

## Requirements
### Requirement: by_yaml runtime MUST accept YAML-shaped `overrides.outputs`
系统 MUST 在 by_yaml runtime 的 `RunOverrides` 中提供 `outputs` 覆盖字段,用于在不修改 demand YAML 的前提下运行期指定输出编排。

`overrides.outputs` 的结构 MUST 与 YAML 顶层 `outputs` 的元素结构一致(YAML-shaped `list[dict]`),但本 change **仅承诺明细输出(detail)**的最小子集,至少包含:
- `name`
- `container`(例如 `type/path/sheet/encoding/include_header/header_fields_output_by/...`)
- `fields`(有序 field_id list)

`overrides.outputs[*]` MUST NOT 支持以下 keys(未来如需支持应另开 change 增量扩展):
- `where`
- `from`
- `aggregate`

#### Scenario: overrides provides a single workbook output
- **GIVEN** demand YAML 未声明 `outputs`
- **WHEN** 调用方在 `run/compile` 中提供 `overrides.outputs` 且其包含一个 `workbook` 输出目标与 `fields` 列表
- **THEN** 本次运行 MUST 以该 `overrides.outputs` 作为 effective outputs
- **AND** 导出字段顺序 MUST 与 `fields` 一致

#### Scenario: overrides provides a single csv output
- **GIVEN** demand YAML 未声明 `outputs`
- **WHEN** 调用方在 `run/compile` 中提供 `overrides.outputs` 且其包含一个 `csv` 输出目标与 `fields` 列表
- **THEN** 本次运行 MUST 以该 `overrides.outputs` 作为 effective outputs

### Requirement: `overrides.outputs` MUST take precedence over YAML `outputs`
系统 MUST 将 `overrides.outputs` 视为最高优先级的输出编排来源。

`overrides.outputs` 提供时 MUST 为非空列表; `overrides.outputs=[]` MUST fail-fast(避免静默“不导出任何东西”)。

#### Scenario: overrides outputs wins over yaml outputs
- **GIVEN** demand YAML 声明了 `outputs` 且包含字段列表 `["a"]`
- **WHEN** 调用方提供 `overrides.outputs` 且包含字段列表 `["b"]`
- **THEN** effective outputs MUST 使用 `["b"]` 而不是 `["a"]`

### Requirement: `overrides.outputs` MUST compile through the same outputs pipeline
系统 MUST 使用与 YAML `outputs` 相同的解析/校验/编译链路来处理 `overrides.outputs`,以避免维护两套输出语义并保证错误信息一致性。

#### Scenario: invalid overrides outputs fails fast with a diagnosable error
- **WHEN** 调用方提供的 `overrides.outputs` 结构非法(例如缺少 `name`/`fields`,或 `container.type` 非法,或包含不支持的 key)
- **THEN** 编译 MUST fail-fast
- **AND** 错误信息 MUST 指向可定位的逻辑路径(例如 `overrides.outputs[0].name`)
