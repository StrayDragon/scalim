## MODIFIED Requirements

### Requirement: Workflow CLI and LSP Guidance Is Explicit
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**`,使其在 workflow YAML 场景下也能提供明确、可复制的校验与 LSP 指引,并与当前实现边界保持一致:

- workflow YAML 仅支持 schema-only 校验（`yaml-dsl schema validate`）；不得引导用户对 workflow YAML 运行 `yaml-dsl validate` 作为“语义校验入口”.
- workflow YAML 的仓库内 schema-only 校验 MUST 提供显式 `--schema` 写法（schema 位置以仓库内 `workflow.gen.json` 为准）。
- workflow YAML 的本地编辑体验 MUST 提供 schema modeline 指引,并使用 `--type workflow` 与 `--comment-style {all,jetbrains,redhat}` 生成适配编辑器/LSP 的 header(不依赖内置 schema server)。

#### Scenario: workflow schema-only 校验指引
- **WHEN** 用户请求校验 workflow YAML
- **THEN** skill 必须提供 `uv run PROJECT_CLI_NAME yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>` 形式的命令
- **THEN** 不得建议直接使用 demand schema 或省略 `--schema`

#### Scenario: workflow LSP modeline 指引
- **WHEN** 用户请求让编辑器对 workflow YAML 提供补全/hover
- **THEN** skill 必须给出 upsert 命令,至少包含:
  - `uv run PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`
- **THEN** 并给出 schema header 示例,至少包含两种格式之一,或同时包含两种格式（当选择 `all` 时）:
  - `# yaml-language-server: $schema=.../workflow.gen.json`
  - `# $schema: .../workflow.gen.json`
