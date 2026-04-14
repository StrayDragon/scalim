# yaml-dsl-project-config-schema (delta) Specification

## ADDED Requirements

### Requirement: scalim.yaml schema generation MUST follow the same SSOT/tooling split as YAML DSL schemas

系统 MUST 将 `scalim.yaml` 的 JSON Schema 生成遵循与 demand/workflow schema 相同的边界约束：

- `scalim.yaml` schema 的结构/描述 SSOT MUST 位于 `src/IMPL_ROOT/dsl/yaml_dsl/schema_dsl/**`
- 生成器实现 MUST 位于 dev tooling packages（例如 `packages/scalim-misc`），并消费 core SSOT
- 生成入口与生成物位置 MUST 仍由 `scripts/gen-yaml-dsl-schema.py` 统一负责

#### Scenario: scalim.yaml generator output is produced by the unified entrypoint
- **WHEN** 维护者执行 `just gen-yaml-dsl-schema`
- **THEN** 系统 MUST 同时生成/刷新 `src/IMPL_ROOT/dsl/yaml_dsl/schema/scalim_yaml.gen.json`

