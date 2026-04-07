# yaml-dsl-project-config-schema (delta)

## ADDED Requirements

### Requirement: `scalim.yaml` schema MUST recursively standardize markdownDescription
系统 MUST 在生成 `scalim.yaml` 的 canonical JSON Schema（`src/IMPL_ROOT/dsl/by_yaml/schema/scalim_yaml.gen.json`）时，对 schema 中的节点递归生成/改写 `markdownDescription`，并使用与 YAML DSL schema 相同的三段式模板：

其 `markdownDescription` MUST 与 YAML DSL schema 采用一致的“brief/full 两套模板”策略（见 `yaml-dsl-schema` delta spec），并且标题行 MUST 使用自动推导的“配置路径”。

其中“配置路径” MUST 由生成器自动推导并包含上下文（例如 `yaml_dsl.import_aliases`），避免仅用字段名导致歧义与漂移。

#### Scenario: every project-config property has structured hover docs
- **WHEN** 维护者执行 `just gen-yaml-dsl-schema`
- **THEN** `scalim_yaml.gen.json` 中 `definitions.*.properties.*` MUST 均包含 `markdownDescription`
- **AND** 其 `markdownDescription` MUST 以 `#### <配置路径>` 标题行开头

### Requirement: project-config doc generation MUST not change discovery semantics
系统 MUST 保持 `scalim.yaml` 的可选性与 nearest-wins project discovery 语义不变；本变更仅增强 schema 的 hover 文档结构与示例展示。

#### Scenario: scalim.yaml remains optional
- **WHEN** 用户的项目不存在 `scalim.yaml`
- **THEN** YAML DSL runtime 与 editor discovery MUST 仍按既有 zero-config fallback 行为工作
