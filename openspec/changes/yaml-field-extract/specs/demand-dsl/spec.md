## ADDED Requirements

### Requirement: source fields support declarative `extract`
系统 SHALL 在 `main_source.fields.*` 与 `sources.*.fields.*` 上支持可选字符串字段 `extract`,用于声明该源字段如何从当前 row value 中读取值。

effective selector 的优先级 MUST 为:
- `extract`
- `field`
- `field_id`

其中:
- `extract` 是新的稳定 authoring surface,支持平铺键名或点路径
- `field` 保持既有语义,仅表示 row value 顶层的 raw key / 列名
- `field` 与 `extract` MUST 互斥

#### Scenario: main_source.fields 使用 `extract`
- **WHEN** `main_source.fields.review_status.extract: review_status`
- **THEN** YAML 校验与 IR 转换 MUST 通过
- **AND** 该字段的 effective selector MUST 为 `review_status`

#### Scenario: 同时声明 `field` 与 `extract` 被拒绝
- **WHEN** 某个源字段同时声明 `field: review_status` 与 `extract: payload.review_status`
- **THEN** 校验 MUST 失败并指向该字段路径

#### Scenario: 未声明 `field` 与 `extract` 时默认回退到 field_id
- **WHEN** 源字段仅声明:
  ```yaml
  review_status:
    name: Review Status
  ```
- **THEN** 该字段的 effective selector MUST 默认为 `review_status`

### Requirement: legacy `field` remains a raw flat selector
系统 MUST 保持 `field` 的既有 flat 语义,不得将其按点路径重新解释。

#### Scenario: `field` 中的点号按字面量顶层键处理
- **GIVEN** 当前 row value 顶层存在字面量键 `customer.info`
- **WHEN** 源字段配置为 `field: customer.info`
- **THEN** 系统 MUST 读取顶层键 `customer.info`
- **AND** MUST NOT 将其拆成 `customer` 与 `info` 两段
