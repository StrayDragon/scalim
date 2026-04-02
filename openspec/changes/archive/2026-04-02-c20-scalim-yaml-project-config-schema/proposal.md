## Why

目前 demand/workflow YAML 已有自动生成的 JSON Schema（`demand.gen.json` / `workflow.gen.json`）可用于编辑器补全与基础结构校验，但项目级配置文件 `scalim.yaml` 还没有对应的 schema。

这会带来几个直接问题：

- 配置 authoring 体验差：不知道 `yaml_dsl.import_aliases` / `yaml_dsl.import_allowed_roots` / `yaml_dsl.editor.*` 能写什么、类型是什么
- 拼写/类型错误往往只能在运行时或 CLI 侧暴露，反馈慢且不够“就地”
- LSP/IDE 集成需要稳定读取 `scalim.yaml` 作为 project discovery 输入，但缺少 schema 使得配置更难落地

同时，`scalim.yaml` 本身是可选配置（zero-config 兜底存在），因此我们更需要“轻量但高质量”的 schema 作为非侵入式增强，而不是引入新的强制控制面。

## What Changes

- 为 `scalim.yaml` 引入 **自动生成** 的 canonical JSON Schema 生成物，用于编辑器补全/校验
- 明确该 schema 的 SSOT/生成入口/漂移门禁：
  - SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`（新增 project-config schema meta）
  - 生成物：`src/scalim/dsl/by_yaml/schema/<scalim-yaml>.gen.json`（命名待定）
  - 生成入口：`just gen-yaml-dsl-schema`（复用现有 schema 生成管线）
  - drift gate：新增/扩展 schema generation 的一致性测试
- 文档补齐：如何在 IDE/LSP 侧绑定 `scalim.yaml` schema；以及 `scalim.yaml` 的 nearest-wins（多层配置）语义说明

## Capabilities

### New Capabilities

- `yaml-dsl-project-config-schema`: 系统提供 `scalim.yaml` 的自动生成 JSON Schema（覆盖 `yaml_dsl.import_aliases` / `yaml_dsl.import_allowed_roots` / `yaml_dsl.editor.python_roots` / `yaml_dsl.editor.kind_overrides`），并将其作为编辑器侧补全与 schema-only 校验的 canonical 入口。

### Modified Capabilities

<!-- 无需求级行为变更则留空 -->

## Impact

- 代码/脚本：
  - schema generation pipeline（`scripts/gen-yaml-dsl-schema.py` + `src/scalim/dsl/by_yaml/schema_dsl/**`）
- 生成物：
  - 新增 `scalim.yaml` JSON schema 生成物（禁止手改；随 `just gen-yaml-dsl-schema` 刷新）
- 文档：
  - `docs/doc/yaml-dsl/editor.md`（增加 scalim.yaml schema 绑定指引）
  - 可能补充 `docs/doc/yaml-dsl/syntax.md`（强调 scalim.yaml 仍是可选，且支持多层 nearest-wins）
