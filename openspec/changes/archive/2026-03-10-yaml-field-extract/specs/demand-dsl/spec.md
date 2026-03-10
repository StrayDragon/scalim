## ADDED Requirements

### Requirement: source fields use `extract` as the only stable field getter
系统 SHALL 在 `main_source.fields.*` 与 `sources.*.fields.*` 上支持可选字符串字段 `extract`,用于声明该源字段如何从当前 key 对应的 row value 中读取值(详见 `yaml-field-extract` 语义与语法约束)。

约束:
- `fields.<field_id>.field` 从稳定 YAML authoring surface 中移除;出现 `field` MUST 在校验/编译阶段 fail-fast,并给出迁移提示: “请改用 extract: ...”
- 若未声明 `extract`,系统 MUST 默认等价于 `extract: <field_id>`(顶层同名 key)

#### Scenario: main_source.fields 使用 `extract`
- **WHEN** `main_source.fields.review_status.extract: review_status`
- **THEN** YAML 校验与 IR 转换 MUST 通过
- **AND** 该字段取值 MUST 等价于读取当前 row value 的顶层 key `review_status`

#### Scenario: legacy `field` 写法被拒绝
- **WHEN** 某个源字段声明 `field: review_status`
- **THEN** 校验 MUST 失败并指向该字段路径
- **AND** 错误 MUST 给出迁移提示: “请改用 extract: review_status”

#### Scenario: 未声明 `extract` 时默认回退到 field_id
- **WHEN** 源字段仅声明:
  ```yaml
  review_status:
    name: Review Status
  ```
- **THEN** 该字段取值 MUST 默认为读取顶层 key `review_status`
