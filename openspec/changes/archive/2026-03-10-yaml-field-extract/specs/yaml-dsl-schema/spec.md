## ADDED Requirements

### Requirement: schema documents `extract` as current-row-relative field extraction
系统 MUST 在 YAML DSL JSON Schema 的源字段定义中新增 `extract` 字段,并在 `description` / `markdownDescription` 中明确说明:
- `extract` 相对当前 key 对应的 row value 解析
- 系统只隐式省略最外层 `lookup_key -> value` 包装
- row value 内部的包裹层不会被自动跳过

schema 示例 MUST 至少包含:
- `extract: CustomerMark.clearn_reason_level`
- `extract: "[1].clearn_reason_level"`
- `extract: '["a.b"]'`
- `extract: review_status`

#### Scenario: schema hover 包含 current-row-relative 说明
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** 源字段定义中的 `extract` MUST 具备 `description` 或 `markdownDescription`
- **AND** 其文案 MUST 明确说明 `extract` 不是相对整个 loader-result mapping 解析

### Requirement: schema removes legacy `field` and provides migration guidance
系统 MUST 从源字段 schema 中移除 `field`,并在 hover/文档中明确说明:
- 源字段取值唯一入口是 `extract`
- rename 也用 `extract: <key_name>`
- 若出现历史 `field: ...`,应按迁移错误处理并提示改为 `extract: ...`

#### Scenario: schema 不再暴露 `field`
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** 源字段定义 MUST NOT 包含可用的 `field` 属性(应通过 schema/validator 拒绝)
