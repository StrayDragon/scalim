# yaml-dsl-project-config-schema Specification

## Purpose
为项目级配置文件 `scalim.yaml` 提供自动生成的 JSON Schema，以获得与 demand/workflow 类似的编辑器补全与 schema-only 校验体验，并将其纳入同一条“SSOT → 生成物 → drift gate”的治理链路。

该 schema 仅描述 **单个** `scalim.yaml` 文件的结构，不改变 `scalim.yaml` 的可选性与 nearest-wins discovery 语义。
## Requirements
### Requirement: Project config MUST ship a canonical JSON Schema for `scalim.yaml`
系统 MUST 提供 `scalim.yaml` 的 canonical JSON Schema 生成物，并将其随仓库提交，以供 IDE/LSP 离线绑定使用。

约束：

- schema MUST 采用 JSON Schema Draft-07（与现有 `demand.gen.json` / `workflow.gen.json` 对齐）
- schema 生成物 MUST 位于 `src/IMPL_ROOT/dsl/by_yaml/schema/` 下（与现有 schema 同目录）
- schema 生成物 MUST 包含 `$comment` 且明确其生成入口（避免误手改）

#### Scenario: schema artifact is present and references the generator
- **WHEN** 维护者在仓库内执行 `just gen-yaml-dsl-schema`
- **THEN** `src/IMPL_ROOT/dsl/by_yaml/schema/` 下 MUST 产出 `scalim.yaml` 的 schema 生成物（文件名按实现约定）
- **AND** 该 schema MUST 包含 `$schema: http://json-schema.org/draft-07/schema#`
- **AND** MUST 包含 `$comment` 指向 schema 生成脚本/入口

### Requirement: `scalim.yaml` schema MUST validate the `yaml_dsl` section used by imports/discovery
`scalim.yaml` schema MUST 至少覆盖当前 runtime/editor 实际读取的配置面：

- `yaml_dsl.import_aliases`
- `yaml_dsl.import_allowed_roots`
- `yaml_dsl.editor.python_roots`
- `yaml_dsl.editor.kind_overrides`

并对关键类型做 schema-level fail-fast（在编辑器侧即可提示）。

#### Scenario: invalid types are rejected by schema-only validation
- **WHEN** 用户将 `yaml_dsl.import_aliases` 写成非 mapping（例如 list/int）
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.import_aliases`

#### Scenario: kind_overrides.kind is constrained
- **WHEN** 用户配置 `yaml_dsl.editor.kind_overrides[0].kind: other`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 指出允许值仅为 `demand|workflow`

### Requirement: Schema generation MUST reuse the existing YAML DSL schema pipeline and be drift-gated
系统 MUST 将 `scalim.yaml` schema 纳入现有 YAML DSL schema 生成管线与漂移门禁中：

- SSOT MUST 位于 `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/**`（不得手写独立 JSON schema 作为 SSOT）
- 生成入口 MUST 复用 `scripts/gen-yaml-dsl-schema.py`（由 `just gen-yaml-dsl-schema` 调用）
- 仓库 MUST 提供 drift gate（测试/脚本）确保生成结果与已提交生成物一致

#### Scenario: drift is detected
- **GIVEN** 维护者修改了 schema SSOT（`schema_dsl`）但未刷新生成物
- **WHEN** 执行仓库 QA/drift gate（例如 schema generation 测试）
- **THEN** gate MUST fail-fast 并提示需要运行 `just gen-yaml-dsl-schema`

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

