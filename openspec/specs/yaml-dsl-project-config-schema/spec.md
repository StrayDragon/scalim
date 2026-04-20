# yaml-dsl-project-config-schema Specification

## Purpose
为项目级配置文件 `scalim.yaml` 提供自动生成的 JSON Schema，以获得与 demand/workflow 类似的编辑器补全与 schema-only 校验体验，并将其纳入同一条”SSOT → 生成物 → drift gate”的治理链路。

该 schema 仅描述 **单个** `scalim.yaml` 文件的结构，不改变 `scalim.yaml` 的可选性与 nearest-wins discovery 语义。

## Related Concepts
- scalim.yaml 项目配置
- JSON Schema (Draft-07)
- schema SSOT (schema_dsl/)
- schema 生成脚本
- drift gate
## Requirements
### Requirement: Project config MUST ship a canonical JSON Schema for `scalim.yaml`
系统 MUST 提供 `scalim.yaml` 的 canonical JSON Schema 生成物，并将其随仓库提交，以供 IDE/LSP 离线绑定使用。

约束：

- schema MUST 采用 JSON Schema Draft-07（与现有 demand/workflow schema 对齐）
- schema 生成物 MUST 位于 schema 目录下（与现有 schema 同目录）
- schema 生成物 MUST 包含 `$comment` 且明确其生成入口（避免误手改）

#### Scenario: schema artifact is present and references the generator
- **GIVEN** schema SSOT 已定义
- **WHEN** 维护者执行 schema 生成命令
- **THEN** schema 目录下 MUST 产出 `scalim.yaml` 的 schema 生成物
- **AND** 该 schema MUST 包含 `$schema: http://json-schema.org/draft-07/schema#`
- **AND** MUST 包含 `$comment` 指向 schema 生成脚本/入口

### Requirement: `scalim.yaml` schema MUST validate the `yaml_dsl` section used by imports/discovery
`scalim.yaml` schema MUST 至少覆盖当前 runtime/editor 实际读取的配置面：

- `yaml_dsl.import_roots`
- `yaml_dsl.lsp.python_roots`
- `yaml_dsl.lsp.kind_overrides`

并对关键类型做 schema-level fail-fast（在编辑器侧即可提示）。

#### Scenario: invalid types are rejected by schema-only validation
- **WHEN** 用户将 `yaml_dsl.import_roots` 写成非 list（例如 mapping/int）
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.import_roots`

#### Scenario: kind_overrides.kind is constrained
- **WHEN** 用户配置 `yaml_dsl.lsp.kind_overrides[0].kind: other`
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误信息 MUST 指出允许值仅为 `demand|workflow`

### Requirement: Schema generation MUST reuse the existing YAML DSL schema pipeline and be drift-gated
系统 MUST 将 `scalim.yaml` schema 纳入现有 YAML DSL schema 生成管线与漂移门禁中：

- SSOT MUST 位于 schema SSOT 目录（不得手写独立 JSON schema 作为 SSOT）
- 生成入口 MUST 复用 schema 生成脚本
- 仓库 MUST 提供 drift gate（测试/脚本）确保生成结果与已提交生成物一致

#### Scenario: drift is detected
- **GIVEN** 维护者修改了 schema SSOT 但未刷新生成物
- **WHEN** 执行仓库 QA/drift gate（例如 schema generation 测试）
- **THEN** gate MUST fail-fast 并提示需要运行 schema 生成命令

### Requirement: scalim.yaml schema generation MUST follow the same SSOT/tooling split as YAML DSL schemas

系统 MUST 将 `scalim.yaml` 的 JSON Schema 生成遵循与 demand/workflow schema 相同的边界约束：

- `scalim.yaml` schema 的结构/描述 SSOT MUST 位于 schema SSOT 目录
- 生成器实现 MUST 位于 dev tooling packages，并消费 core SSOT
- 生成入口与生成物位置 MUST 仍由 schema 生成脚本统一负责

#### Scenario: scalim.yaml generator output is produced by the unified entrypoint
- **GIVEN** schema SSOT 已定义
- **WHEN** 维护者执行 schema 生成命令
- **THEN** 系统 MUST 同时生成/刷新 `scalim.yaml` 的 schema 生成物

### Requirement: `scalim.yaml` schema MUST reject runtime runner config
系统 MUST 将 `scalim.yaml` 的 `yaml_dsl` 段落限制为 imports + LSP/discovery 配置面，并且 MUST 拒绝任何 runtime runner defaults 配置（例如 `yaml_dsl.runner`）。

#### Scenario: yaml_dsl.runner is rejected
- **WHEN** 用户在 `scalim.yaml` 中配置 `yaml_dsl.runner.allowed_modules`
- **THEN** schema-only 校验 MUST 失败并指向 `yaml_dsl.runner`
