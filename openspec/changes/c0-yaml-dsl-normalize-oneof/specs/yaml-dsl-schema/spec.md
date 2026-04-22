## MODIFIED Requirements

### Requirement: schema 说明源代码级 `normalize` 及其执行顺序

系统 MUST 在 YAML DSL JSON Schema 的 `sources.*` 定义中新增 `normalize` 字段，并在 `description` / `markdownDescription` 中明确说明：
- `normalize` 是源代码级整体结果归一化
- `normalize` 先于字段级 `extract` 执行
- `normalize.index_by_key` 的输入输出形状示例

约束：
- `main_source` MUST NOT 暴露 `normalize` 字段
- `sources.*.normalize` MUST 以分支 one-of 结构表达，并且必须且只能选择一个 normalize 分支：
  - `index_by_key` / `take_first` / `project_fields` / `map_values`
  - `normalize` MAY 额外声明公共字段 `call_by`
- `sources.*.normalize.index_by_key.on_none` MUST 为 `raise|skip`
- 仅当 `sources.*.normalize` 选择 `index_by_key` 分支时允许出现 `on_none`
- 当 `sources.*.normalize` 为其它分支且出现 `on_none` 时，系统 MUST 拒绝该配置

#### Scenario: schema hover 包含 normalize 说明
- **WHEN** 生成 demand JSON Schema
- **THEN** `sources.*.normalize` 的文案 MUST 展示形状示例
- **AND** MUST 明确说明该能力不是字段级提取

#### Scenario: normalize 约束校验
- **WHEN** `main_source` 包含 `normalize`，或 `sources.*.normalize` 为非 `index_by_key` 分支但仍声明 `on_none`
- **THEN** schema/运行时校验 MUST 失败并指出错误
