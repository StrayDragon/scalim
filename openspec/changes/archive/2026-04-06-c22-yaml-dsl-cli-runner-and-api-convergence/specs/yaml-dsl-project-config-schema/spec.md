# yaml-dsl-project-config-schema (delta) Specification

## ADDED Requirements

### Requirement: `scalim.yaml` schema MUST cover `yaml_dsl.runner` defaults for CLI runner
系统 MUST 扩展 `scalim.yaml` schema 以覆盖 CLI runner 所需的项目级默认值配置面（可选）：

- `yaml_dsl.runner.allowed_modules`
- `yaml_dsl.runner.allowed_functions`
- `yaml_dsl.runner.allowed_yaml_roots`
- `yaml_dsl.runner.template_sandbox`
- `yaml_dsl.runner.parallel_mode`
- `yaml_dsl.runner.max_workers`

这些字段 MUST 保持为可选（不改变 `scalim.yaml` 的可选性与 nearest-wins discovery 语义），其目的仅为减少 CLI/Python 运行时重复传参并提升可复现性。

#### Scenario: schema-only validation rejects invalid runner types
- **WHEN** 用户将 `yaml_dsl.runner.allowed_modules` 写成非 list（例如 string/int）
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.runner.allowed_modules`

#### Scenario: schema constrains template_sandbox choices
- **WHEN** 用户配置 `yaml_dsl.runner.template_sandbox: other`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 指出允许值为实现支持的集合（例如 `safe|legacy`）

### Requirement: runner defaults MUST NOT weaken allowlist semantics
系统 MUST 确保 `yaml_dsl.runner` 的默认值配置不会弱化 allowlist 语义：若项目配置提供了 `yaml_dsl.runner.allowed_modules/allowed_functions`，该配置仅用于“提供默认 allowlist 值”。

系统 MUST 保持 allowlist 为空时 fail-fast 的语义；项目配置 MUST NOT 被解释为“允许任意 import”或“跳过 allowlist 检查”。

#### Scenario: empty allowlist still fails fast
- **GIVEN** `scalim.yaml` 存在但未配置 `yaml_dsl.runner.allowed_modules/allowed_functions`
- **WHEN** 调用方尝试通过 CLI runner 运行 demand/workflow YAML
- **THEN** 系统 MUST fail-fast 并提示如何配置 allowlist
