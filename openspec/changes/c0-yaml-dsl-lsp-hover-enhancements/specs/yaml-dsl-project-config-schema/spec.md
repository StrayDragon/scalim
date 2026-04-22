## MODIFIED Requirements

### Requirement: `scalim.yaml` schema MUST validate the `yaml_dsl` section used by imports/discovery
`scalim.yaml` schema MUST 至少覆盖当前 runtime/editor 实际读取的配置面：

- `yaml_dsl.import_roots`
- `yaml_dsl.lsp.python_roots`
- `yaml_dsl.lsp.kind_overrides`
- `yaml_dsl.lsp.hover`

并对关键类型做 schema-level fail-fast（在编辑器侧即可提示）。

#### Scenario: invalid types are rejected by schema-only validation
- **WHEN** 用户将 `yaml_dsl.import_roots` 写成非 list（例如 mapping/int）
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.import_roots`

#### Scenario: kind_overrides.kind is constrained
- **WHEN** 用户配置 `yaml_dsl.lsp.kind_overrides[0].kind: other`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 指出允许值仅为 `demand|workflow`

#### Scenario: hover field names are constrained
- **WHEN** 用户配置 `yaml_dsl.lsp.hover.field_reference: [\"unknown_field\"]`
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.lsp.hover.field_reference[0]`
