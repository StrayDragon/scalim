## ADDED Requirements

### Requirement: schema documents `extract` as current-row-relative field extraction
系统 MUST 在 YAML DSL JSON Schema 的源字段定义中新增 `extract` 字段,并在 `description` / `markdownDescription` 中明确说明:
- `extract` 相对当前 key 对应的 row value 解析
- 系统只隐式省略最外层 `lookup_key -> value` 包装
- row value 内部的包裹层不会被自动跳过

schema 示例 MUST 至少包含:
- `extract: CustomerMark.clearn_reason_level`
- `extract: review_status`

#### Scenario: schema hover 包含 current-row-relative 说明
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** 源字段定义中的 `extract` MUST 具备 `description` 或 `markdownDescription`
- **AND** 其文案 MUST 明确说明 `extract` 不是相对整个 loader-result mapping 解析

### Requirement: schema distinguishes `extract` from legacy `field`
系统 MUST 在 schema hover 中明确区分:
- `extract`: 新的 declarative 提取语法,支持点路径
- `field`: 既有 raw flat selector,不做点路径拆分

#### Scenario: schema hover 说明 `field` 不做点路径拆分
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** 源字段定义中的 `field` 文案 MUST 提及其 raw flat selector 语义
- **AND** MUST 提示 dotted path 应改用 `extract`
