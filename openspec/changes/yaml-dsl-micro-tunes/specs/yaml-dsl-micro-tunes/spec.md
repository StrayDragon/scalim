## ADDED Requirements

### Requirement: Relation references support string ref to relations.<id>
系统 MUST 支持在字段定义中用字符串引用 relation:
- `relation: <relation_id>` 作为 `relations.<relation_id>` 的显式引用

系统 MUST 在 full validate 时校验:
- `relations.<relation_id>` 存在
- relation steps 的起止字段与 chain 校验规则保持不变

#### Scenario: relation can be referenced by id
- **WHEN** 用户在字段中写 `relation: orders_to_customers`
- **THEN** 系统 MUST 将其解析为对 `relations.orders_to_customers` 的引用,并执行与 steps 对象相同的语义校验

#### Scenario: unknown relation id is rejected
- **WHEN** 用户写 `relation: missing_relation`
- **THEN** full validate MUST 失败,并指出缺失的 `relations.missing_relation`

### Requirement: output.fields supports string list sugar
系统 MUST 支持 `output.fields` 的 string sugar:
- string 作为 `field_id`(例如 `order_id`)
- `source.field_id` 作为显式消歧形式(例如 `orders.order_id`)

系统 MUST 保留对象条目用于覆写字段输出行为(例如覆写 `name` 或指定 selector)。

#### Scenario: output.fields accepts field_id strings
- **WHEN** 用户写 `output.fields: [order_id, order_date]`
- **THEN** schema-only 校验与 full validate MUST 通过,并按声明顺序输出字段

#### Scenario: output.fields accepts source.field_id strings
- **WHEN** 用户写 `output.fields: [orders.order_id, customers.customer_name]`
- **THEN** full validate MUST 将其解析为显式选择器,避免同名字段歧义

### Requirement: Derived fields are declared under derived_fields (breaking)
系统 MUST 使用顶层 `derived_fields` 作为派生字段入口,并在该入口下允许 `compute/call_by` 等派生字段能力。
系统 MUST NOT 接受顶层 `fields` 作为派生字段入口。

#### Scenario: derived fields live under derived_fields
- **WHEN** 用户写 `derived_fields: {order_amount: {compute: \"...\"}}`
- **THEN** full validate MUST 识别其为派生字段,并按既有派生字段规则进行校验

#### Scenario: legacy fields key is rejected
- **WHEN** 用户仍使用顶层 `fields`
- **THEN** full validate MUST 失败,并提示改用 `derived_fields`

### Requirement: Runtime vars use directive node form (breaking)
系统 MUST 支持并统一 runtime vars 的指令节点形态:
- `{$runtime: <name>}`

系统 MUST NOT 依赖字符串占位符 `$runtime.<name>` 作为 runtime vars 表达。

#### Scenario: runtime var directive is accepted
- **WHEN** 用户在 params 中写 `ids: {$runtime: order_ids}`
- **THEN** schema-only 校验与 full validate MUST 通过,并在运行期注入对应 runtime 值

#### Scenario: legacy $runtime.xxx placeholder is rejected
- **WHEN** 用户在 params 中写 `ids: \"$runtime.order_ids\"`
- **THEN** full validate MUST 失败,并提示改用 `{$runtime: order_ids}`

### Requirement: Validator provides actionable diagnostics for field_id vs data_key mistakes
当 relation steps 写了 data_key(不在声明字段与 key 中)时,系统 MUST 在错误信息中提供:
- 最可能的 `field_id` 建议(至少 1 个)
- 可直接复制的修复片段(最小 YAML 片段)

#### Scenario: validator suggests likely field_id and fix snippet
- **WHEN** 用户在 relation steps 中误写 data_key
- **THEN** full validate MUST 失败,并在错误信息中包含建议的 `field_id` 与可复制的修复片段
