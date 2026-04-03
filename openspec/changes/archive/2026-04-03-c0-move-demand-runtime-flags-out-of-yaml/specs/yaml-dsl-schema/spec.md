# yaml-dsl-schema Specification

## REMOVED Requirements

### Requirement: schema exposes a switch for unique effective field display names
**Reason**: `validate_unique_field_names` 属于 demand runtime policy,不应作为可复制传播的 YAML mainline authoring 字段。

**Migration**:
- 从 demand YAML 顶层移除 `validate_unique_field_names`
- 通过 Python/CLI runtime entrypoints 配置 `validate_unique_field_names`(默认 `true`)

#### Scenario: schema no longer exposes validate_unique_field_names
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** schema MUST NOT 暴露 `properties.validate_unique_field_names`

## ADDED Requirements

### Requirement: schema MUST NOT expose include_full_error_message
`include_full_error_message` 属于 runtime policy(可能包含敏感信息),系统 MUST 不再将其作为 demand YAML stable authoring 字段暴露在 schema 中。

#### Scenario: schema no longer exposes include_full_error_message
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** schema MUST NOT 暴露 `properties.include_full_error_message`

