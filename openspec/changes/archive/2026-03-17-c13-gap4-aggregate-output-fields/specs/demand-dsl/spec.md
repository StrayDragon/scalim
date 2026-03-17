## ADDED Requirements

### Requirement: aggregate outputs MUST allow explicit output field layout
系统 MUST 允许在声明了 `outputs.*.aggregate` 的 output 上同时声明 `outputs.*.fields`,用于“输出合同编排”(select + order),而不改变聚合计算语义.

#### Scenario: aggregate output declares fields for ordering
- **GIVEN** 某个 output 同时声明 `aggregate` 与 `fields`
- **WHEN** demand 被编译并运行输出
- **THEN** 输出列顺序 MUST 以 `outputs.*.fields` 声明顺序为准

### Requirement: aggregate fields MAY provide display name for headers
系统 MUST 允许 `outputs.*.aggregate.fields.<out_field_id>` 声明可选 `name` 作为显示名.
当 `outputs.*.container.header_fields_output_by: name` 时,系统 MUST 使用该显示名作为表头输出,且 MUST 允许重复 `name` 以支持重复表头合同.

#### Scenario: aggregate field display names are used as headers
- **GIVEN** aggregate field 声明 `name`,且 output container 设置 `header_fields_output_by: name`
- **WHEN** output 写出表头
- **THEN** 表头 MUST 使用该 `name` 值,并允许多个字段输出相同的表头文本

