## MODIFIED Requirements

### Requirement: schema hover 提供常见错误与迁移提示
系统 MUST 在 YAML DSL JSON Schema 的关键字段上提供可读且简短的常见错误/迁移提示,以提升编辑器 LSP 体验并减少试错成本:

- `relations.*.steps.from/to` 的 hover MUST 提示 steps 仅接受 **field_id**(YAML key)而非 loader 的 data_key,并给出简短示例.
- `lookup_cast` 的 hover MUST 提示 float lookup key 会被拒绝(避免歧义)并建议通过 `lookup_cast`/`value_cast` 显式归一化.
- `main_source.params`/`sources.*.params` 的 hover MUST 解释 `{$init_var: <name>}`/`$keys/$rows` 的用法与限制,并说明 legacy `bind/to_bind` 已移除并迁移到 `params` 模板.

#### Scenario: hover 包含 field_id/data_key 提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `relations.*.steps.from/to` 的 `markdownDescription` MUST 提及 field_id 与 data_key 的区别并包含示例

#### Scenario: hover 包含 float key 策略提示
- **WHEN** 生成 `demand.gen.json`
- **THEN** `lookup_cast` 的 `markdownDescription` MUST 提示 float 被拒绝并给出修复建议

### Requirement: `params` hover documents `{$runtime: <name>}` and preload params behavior
Schema 生成器 MUST 在 `main_source.params` 与 `sources.*.params` 的 hover/markdownDescription 中清晰说明:
- `main_source.params` 作为 kwargs 直接透传给 main source loader
- `sources.<id>.params` 作为 loader kwargs 模板,在对应 loader 被调用时透传(包含 preload_forever 的预加载调用)
- `{$init_var: <name>}` 可用于引用初始化变量,并在编译期被解析为调用方提供的 `init_vars[<name>]`

#### Scenario: schema hover 不再声称 preload_forever 零参调用
- **WHEN** 生成 `demand.gen.json`
- **THEN** `sources.*.params` 的 markdownDescription MUST 不再包含“preload_forever 预加载调用为无参”的旧描述
