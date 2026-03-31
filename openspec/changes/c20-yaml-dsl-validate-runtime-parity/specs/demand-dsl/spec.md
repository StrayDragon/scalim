## ADDED Requirements

### Requirement: source_id and sources keys MUST be valid identifiers and validated fail-fast
系统 MUST 对以下标识执行一致的 identifier 校验,并在 validate/schema validate 阶段 fail-fast(避免 compile/runtime 才失败):

- `main_source.source_id`
- `sources` mapping keys(每个 source 的 `source_id`)

identifier 规则 MUST 为正则: `^[a-zA-Z_][a-zA-Z0-9_]*$`。

并且当 source 声明存在时:

- `main_source.loader` MUST 为非空字符串
- `sources.<id>.loader` MUST 为非空字符串
- `sources.<id>.key` MUST 为非空字段名(或非空字段名列表)

#### Scenario: invalid source_id is rejected early
- **WHEN** `main_source.source_id` 或 `sources` 的 key 为 `\"\"` 或 `\"1abc\"`
- **THEN** `scalim-cli yaml-dsl validate` MUST 失败
- **AND** 错误 MUST 可定位到 `main_source.source_id` 或 `sources`(并指出非法 key)

#### Scenario: empty loader/key is rejected early
- **WHEN** `sources.orders.loader: \"\"` 或 `sources.orders.key: \"\"`
- **THEN** `scalim-cli yaml-dsl validate` MUST 失败
- **AND** 错误 MUST 指向 `sources.orders.loader`/`sources.orders.key`

