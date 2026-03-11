## ADDED Requirements

### Requirement: schema 说明源级 `normalize` 及其执行顺序
系统 MUST 在 YAML DSL JSON Schema 的 `sources.*` 定义中新增 `normalize` 字段,并在 `description` / `markdownDescription` 中明确说明:
- `normalize` 是源级整体结果归一化
- `normalize` 先于字段级 `extract` 执行
- `normalize.kind=index_by_key` 的输入输出形状示例

#### Scenario: schema hover 包含 `index_by_key` 形状示例
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `sources.*.normalize` 的文案 MUST 展示 `list[row] -> key -> row` 的示例
- **AND** MUST 明确说明该能力不是字段级提取

### Requirement: schema keeps `normalize` out of `main_source`
系统 MUST NOT 在 `main_source` schema 中暴露 `normalize` 字段。

#### Scenario: `main_source` schema 无 `normalize`
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `definitions.main_source.properties` MUST NOT 包含 `normalize`
