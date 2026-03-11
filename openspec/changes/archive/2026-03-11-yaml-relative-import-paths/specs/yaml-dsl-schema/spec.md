## ADDED Requirements

### Requirement: schema hover 说明 loader 引用支持相对模块语法
系统 MUST 在 YAML DSL JSON Schema 中为 `main_source.loader` / `sources.*.loader` / `*.retry.should_retry` 的 hover 文案说明 loader 引用格式,并明确:
- 支持绝对引用 `module.path.function` / `module.path:obj.method`
- 支持以 `.` / `..` 开头的相对模块路径(相对 YAML 文件所在目录)
- 相对引用解析后仍受白名单(`allowed_modules`/`allowed_functions`)约束

#### Scenario: loader hover 提示包含相对引用示例
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `main_source.loader` 的 `markdownDescription` MUST 包含至少一个相对引用示例(例如 `.loaders:load_orders`)

## MODIFIED Requirements

### Requirement: 派生字段支持 call_by Schema
Schema 生成器 SHALL 在派生字段定义中加入 `call_by` 字段,类型为字符串,并在 schema hover 中说明 `reference(args...)` 语法、kwargs 示例、Python 字面量示例与 `$ctx.*` 可用属性( `row_id`/`batch_num`/`field_id`/`deps`/`values` ).
schema hover MUST 明确 `reference` 的模块路径同时支持:
- 绝对引用: `module.path.function` / `module.path:obj.method`
- 相对引用: 以 `.` / `..` 开头的模块路径(相对 YAML 文件所在目录)

Schema SHALL 对派生字段声明 `compute` 与 `call_by` 做互斥约束(oneOf),并确保源字段/主源字段不允许出现 `call_by`.

#### Scenario: call_by 仅允许派生字段
- **WHEN** `main_source.fields` 或 `sources.*.fields` 中出现 `call_by`
- **THEN** schema 校验失败并提示仅允许派生字段

#### Scenario: call_by 语法说明可见且包含相对引用
- **WHEN** 在 LSP/Schema hover 查看 `call_by`
- **THEN** 显示函数引用格式、kwargs 示例与 `$ctx.*` 可用属性说明
- **AND** hover MUST 包含至少一个相对引用示例(例如 `.helpers:to_text(status)`)

#### Scenario: compute/call_by 互斥
- **WHEN** 同一派生字段同时声明 `compute` 与 `call_by`
- **THEN** schema 校验失败并提示互斥约束
