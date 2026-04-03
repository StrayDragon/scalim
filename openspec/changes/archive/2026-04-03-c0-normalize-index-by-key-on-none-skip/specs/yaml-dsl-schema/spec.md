## ADDED Requirements

### Requirement: schema/validator restrict `normalize.on_none` to `index_by_key`

系统 MUST 在生成的 YAML DSL JSON Schema 与运行时 validate 中对 `sources.*.normalize.on_none` 提供受控扩展,并满足:

- `sources.*.normalize.on_none` MUST 为 `raise|skip`
- 仅当 `sources.*.normalize.kind=index_by_key` 时允许出现 `on_none`
- 当 `sources.*.normalize.kind` 为其它值且出现 `on_none` 时,系统 MUST 拒绝该配置(不得静默忽略)

#### Scenario: schema validate accepts `on_none=skip` for `index_by_key`
- **WHEN** demand YAML 配置包含:
  ```yaml
  sources:
    orders:
      kind: lookup
      loader: {call_by: mypkg.load_orders}
      normalize:
        kind: index_by_key
        key_field: order_id
        on_none: skip
  ```
- **THEN** schema-only 校验 MUST 通过

#### Scenario: schema validate rejects `on_none` for non-`index_by_key`
- **WHEN** demand YAML 配置包含:
  ```yaml
  sources:
    orders:
      kind: lookup
      loader: {call_by: mypkg.load_orders}
      normalize:
        kind: project_fields
        on_none: skip
  ```
- **THEN** schema-only 校验 MUST 失败并指出字段路径

#### Scenario: runtime validate rejects `on_none` for non-`index_by_key`
- **WHEN** 用户配置 `sources.orders.normalize.kind=project_fields` 且包含 `sources.orders.normalize.on_none=skip`
- **THEN** 运行时 validate MUST fail-fast 并明确指出 `on_none` 仅对 `index_by_key` 有效
