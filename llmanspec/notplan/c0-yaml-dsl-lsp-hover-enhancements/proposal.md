> 一句话描述: 为 YAML DSL LSP 提供可配置、Markdown 结构化的 hover cards（`scalim.yaml yaml_dsl.lsp.hover` 控制展示字段与顺序）。

## Why

当前 `scalim-yaml-dsl-lsp` 的 hover 输出以纯文本为主且信息密度偏低（尤其是 relation steps 的 `source.field_id`、`call_by` 参数中的字段 token 等场景），用户需要更“像卡片”的结构化信息来快速理解引用含义、定位声明与排障。与此同时，YAML LSP + JSON Schema 已能提供字段 schema 级描述，因此 DSL hover 更应聚焦“引用语义 + 上下文”，并支持按项目配置调节展示粒度。

## What Changes

- 为 `scalim.yaml` 新增 `yaml_dsl.lsp.hover` 配置面：按 hover 类型配置展示字段列表与顺序，并提供稳定的默认值。
- 扩展 `scalim.yaml` JSON Schema（generated）以支持 `yaml_dsl.lsp.hover.*` 的补全与 schema-only 校验（枚举值约束）。
- `scalim-yaml-dsl-lsp` hover 输出升级为 Markdown，并重构 hover 生成逻辑：
  - field / entity / python / builtin callable / aggregate / call_by kwargs value 等 hover 支持按配置渲染。
  - 输出避免与 schema hover 重复：优先提供“解析后的语义信息”（例如定位声明、关联上下文摘要、签名/定义位置等）。
- 明确 SSOT vs 生成物边界：
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py` 为 schema SSOT
  - `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json` 为生成物（通过 `just gen-yaml-dsl-schema` 刷新；禁止手工编辑）

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-hover`: 为 YAML DSL LSP 提供可配置、Markdown 结构化的 hover cards（通过 `scalim.yaml yaml_dsl.lsp.hover` 控制展示字段与顺序）。

### Modified Capabilities
- `yaml-dsl-project-config-schema`: `scalim.yaml` schema MUST 覆盖并校验 `yaml_dsl.lsp.hover.*`（作为 imports/discovery/LSP 的项目配置面的一部分）。

## Impact

- 受影响代码：
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py`（解析与校验 `yaml_dsl.lsp.hover`；Python 3.6 边界）
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py`（schema SSOT）
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`、`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`（hover 渲染与 MarkupKind）
- 受影响生成物：
  - `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`（由 `just gen-yaml-dsl-schema` 生成；drift gate 覆盖）
- 受影响文档/示例：
  - LSP/VSCode 相关 fixtures 或示例 `scalim.yaml`（用于展示 hover 配置用法）
