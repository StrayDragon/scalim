## MODIFIED Requirements

### Requirement: `scalim.yaml` schema MUST validate the `yaml_dsl` section used by imports/discovery
`scalim.yaml` schema MUST 至少覆盖当前 runtime/editor 实际读取的配置面：

- `yaml_dsl.import_aliases`
- `yaml_dsl.import_allowed_roots`
- `yaml_dsl.lsp.python_roots`
- `yaml_dsl.lsp.kind_overrides`

并对关键类型做 schema-level fail-fast（在编辑器侧即可提示）。

#### Scenario: invalid types are rejected by schema-only validation
- **WHEN** 用户将 `yaml_dsl.import_aliases` 写成非 mapping（例如 list/int）
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.import_aliases`

#### Scenario: kind_overrides.kind is constrained
- **WHEN** 用户配置 `yaml_dsl.lsp.kind_overrides[0].kind: other`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 指出允许值仅为 `demand|workflow`

## REMOVED Requirements

### Requirement: `scalim.yaml` schema MUST cover `yaml_dsl.runner` defaults for CLI runner
**Reason**：本变更移除 CLI 执行入口；`scalim.yaml` 收敛为 authoring/tooling 配置，不再承载运行期 defaults。

**Migration**：将原 `yaml_dsl.runner.*` 默认值移动到 Python 运行入口的装配代码（`RunOptions`），由应用/调度系统统一管理。

#### Scenario: project config no longer defines runner defaults
- **WHEN** 用户在 `scalim.yaml` 中配置 `yaml_dsl.runner.*`
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.runner`

### Requirement: runner defaults MUST NOT weaken allowlist semantics
**Reason**：runner defaults 被移除；allowlist 的唯一入口为 Python `RunOptions.allowed_modules/allowed_functions`，安全边界由 runtime fail-fast 保证。

**Migration**：在执行入口显式装配 allowlist；不得再通过 `scalim.yaml` 注入 allowlist 默认值。

#### Scenario: allowlist remains explicit at execution time
- **WHEN** 用户通过 Python 入口执行 YAML
- **THEN** 系统 MUST 要求显式 allowlist（空 allowlist 仍 fail-fast）

## ADDED Requirements

### Requirement: `scalim.yaml` schema MUST reject runtime runner config
系统 MUST 将 `scalim.yaml` 的 `yaml_dsl` 段落限制为 imports + LSP/discovery 配置面，并且 MUST 拒绝任何 runtime runner defaults 配置（例如 `yaml_dsl.runner`）。

#### Scenario: yaml_dsl.runner is rejected
- **WHEN** 用户在 `scalim.yaml` 中配置 `yaml_dsl.runner.allowed_modules`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 指向 `yaml_dsl.runner` 为未知/不支持字段

