# yaml-dsl-runtime-policy-boundary Specification

## MODIFIED Requirements

### Requirement: demand runtime-policy fields MUST move out of YAML mainline
demand 侧明显属于 runtime policy 的字段 MUST 从 YAML 主线迁出到 Python / CLI runtime entrypoints:

- `guardrails.*` MUST 迁出 YAML
- `retry.*` MUST 迁出 YAML
- `batch_size` MUST 迁出 YAML
- demand `failure_policy` MUST 迁出 YAML
- `include_full_error_message` MUST 迁出 YAML
- `validate_unique_field_names` MUST 迁出 YAML

#### Scenario: demand runtime-policy fields in YAML are rejected with migration guidance
- **GIVEN** 某个 demand YAML 仍声明 `include_full_error_message` 或 `validate_unique_field_names`
- **WHEN** 用户执行 validate 或运行入口解析
- **THEN** 系统 MUST 拒绝其作为主线 authoring 字段
- **AND** MUST 给出迁移到 runtime entrypoint 的提示

