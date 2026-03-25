# yaml-dsl-schema Specification

## Purpose
更新 YAML DSL JSON Schema 的 authoring guidance,使其与现行 `outputs` 语法表面与运行期 `overrides.outputs` 推荐用法一致,并暴露“字段展示名唯一性”校验开关。

## REMOVED Requirements

### Requirement: output 字段 hover 指引明确可选与 overrides 推荐写法
**Reason**: 顶层 `output:` 已不是稳定 YAML authoring surface(已 fail-fast),继续在 schema 中强调 `output` 与 `overrides.output.*` 会误导下游走旧路径并与 `outputs`/`overrides.outputs` 的标准做法冲突。

**Migration**: 使用顶层 `outputs:`(可选)表达输出编排;当需要运行时动态指定输出(字段/路径/sheet/header 策略)时,推荐在 Python 调用侧使用与 YAML 同形的 `overrides.outputs` 覆盖。

## ADDED Requirements

### Requirement: outputs 字段 hover 指引明确可选与 overrides 推荐写法
系统 MUST 在生成的 YAML DSL JSON Schema 中,为顶层 `outputs` 字段提供清晰的 `markdownDescription`,并明确:
- 顶层 `outputs` 为可选字段(用于保持 demand YAML 可复用);
- 当把 demand YAML 当作“需求本体模板”复用时,推荐在 Python 调用侧使用 `overrides.outputs` 运行期指定输出编排。

#### Scenario: schema 中包含 outputs 可选与 overrides.outputs 提示
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `properties.outputs.markdownDescription` MUST 提及 `outputs` 可选
- **AND** `properties.outputs.markdownDescription` MUST 提及 `overrides.outputs` 的推荐用法

### Requirement: `header_fields_output_by` default is `name`
系统 MUST 将 `outputs[*].container.header_fields_output_by` 的 schema 默认值设为 `name`(破坏性变更)。

#### Scenario: schema default for header_fields_output_by is name
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `definitions.output_container.properties.header_fields_output_by.default` MUST 等于 `name`

### Requirement: schema exposes a switch for unique effective field display names
系统 MUST 在 schema 中暴露一个 YAML authoring 侧开关,用于控制“字段有效展示名(effective display name)全局唯一”的预检查策略。

该开关 MUST:
- 位于顶层;
- 名称为 `validate_unique_field_names`(boolean);
- 默认语义为启用(未声明时等价 `true`);
- hover 文案 MUST 解释“有效展示名”的定义: `field.name` 非空则取 `name`,否则回退为 `field_id`。
- hover 文案 MUST 说明该预检查仅在 effective outputs 使用 `container.include_header: true`(显式或默认) 且 `container.header_fields_output_by: name` 时触发。

#### Scenario: schema 生成结果包含顶层校验开关
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** schema MUST 暴露 `properties.validate_unique_field_names`
