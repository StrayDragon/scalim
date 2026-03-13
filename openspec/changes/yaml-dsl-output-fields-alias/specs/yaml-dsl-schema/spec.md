## ADDED Requirements

### Requirement: `outputs.*.fields` 支持 YAML alias 条目
系统 MUST 允许 `outputs[*].fields` 的每一项为以下两种之一:
- `field_id` 字符串
- YAML alias(object) 条目: 条目为某个“已定义字段对象”的 alias(展开后为 dict),系统 MUST 将其解析为该字段对象对应的 `field_id`

字段对象的来源包括:
- `main_source.fields.*`
- `sources.*.fields.*`
- 顶层派生字段 `fields.*`

#### Scenario: `outputs.*.fields` 使用 main_source 字段 alias
- **GIVEN** `main_source.fields.quantity: &quantity {...}` 定义了字段对象
- **WHEN** `outputs[0].fields` 包含条目 `- *quantity`
- **THEN** 校验 MUST 通过且解析后的 `outputs[0].fields` MUST 包含 `quantity` 作为 `field_id`

#### Scenario: `outputs.*.fields` 使用 derived 字段 alias
- **GIVEN** 顶层 `fields.profit: &profit {compute: ...}` 定义了派生字段对象
- **WHEN** `outputs[0].fields` 包含条目 `- *profit`
- **THEN** 校验 MUST 通过且解析后的 `outputs[0].fields` MUST 包含 `profit` 作为 `field_id`

### Requirement: alias identity 失败时允许唯一内容匹配
当 `outputs[*].fields` 的 object 条目无法通过“对象身份”(identity)反查到字段对象时,系统 SHALL 允许基于内容相等做兜底匹配,但仅当匹配结果唯一时才允许成功解析.

#### Scenario: content match 唯一匹配成功
- **GIVEN** `outputs[0].fields[0]` 为一个 dict,其内容与某个已定义字段对象内容相等且仅能匹配到一个字段
- **WHEN** 系统解析 `outputs`
- **THEN** 该条目 MUST 被解析为该字段的 `field_id`

#### Scenario: content match 歧义时 fail-fast
- **GIVEN** `outputs[0].fields[0]` 的 dict 内容可匹配到多个字段对象
- **WHEN** 系统解析 `outputs`
- **THEN** 校验 MUST 失败并提示该条目歧义,并建议改用 string `field_id`

#### Scenario: content match 找不到时 fail-fast
- **GIVEN** `outputs[0].fields[0]` 的 dict 内容无法匹配任何字段对象
- **WHEN** 系统解析 `outputs`
- **THEN** 校验 MUST 失败并提示该条目无法解析为 `field_id`,并建议改用 string `field_id`

### Requirement: schema 允许 `outputs.*.fields` 包含 object 条目
系统 MUST 在生成的 YAML DSL JSON Schema 中允许 `outputs[*].fields.items` 为 `string | object`,以避免 schema-only 校验与编辑器提示拦截 alias 写法.

#### Scenario: schema validate 不因 object 条目直接失败
- **GIVEN** `outputs[0].fields` 包含 YAML alias(object) 条目
- **WHEN** 执行 schema-only 校验
- **THEN** 校验 MUST NOT 因 `outputs[0].fields[*]` 的类型为 object 而失败
