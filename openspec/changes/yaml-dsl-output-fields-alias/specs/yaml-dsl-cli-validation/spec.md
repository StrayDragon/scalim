## ADDED Requirements

### Requirement: validate 对 `outputs.*.fields` object 条目给出可行动诊断
系统 MUST 在 `PROJECT_CLI_NAME yaml-dsl validate` 的内部语义校验中,对 `outputs[*].fields` 的 object 条目执行解析校验:

- 若 object 条目无法解析为唯一 `field_id`,校验 MUST 失败
- 错误 MUST 包含可行动提示(例如候选 `field_id` 列表/歧义原因/建议改用 string `field_id`)
- 错误 MUST 以 `outputs.<i>.fields.<j>` 作为定位路径,以便 CLI 能附加正确的 `path:line[:column]`

#### Scenario: object 条目无法解析时报错并提示改用 field_id
- **GIVEN** `outputs[0].fields[0]` 为 object 条目且无法匹配到任何字段定义
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误消息 MUST 提示该条目无法解析为 `field_id` 并建议改用 string `field_id`

#### Scenario: object 条目歧义时报错并列出候选字段
- **GIVEN** `outputs[0].fields[0]` 为 object 条目且可匹配到多个字段定义
- **WHEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <yaml>`
- **THEN** 校验 MUST 失败
- **AND** 错误消息 MUST 包含候选字段的 `field_id` 列表并建议改用 string `field_id`
