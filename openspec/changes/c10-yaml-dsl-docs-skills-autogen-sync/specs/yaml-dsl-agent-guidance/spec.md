## MODIFIED Requirements

### Requirement: CLI and LSP Guidance Is Explicit
手工维护的 skill MUST 直接提供可复制的 CLI/LSP 指引,覆盖仓库内与脱离仓库两种使用方式。

同时，为避免命令文案随实现演进而漂移，该指引中的“可复制命令片段” MUST 通过 injected blocks 受控注入，并以 CLI parser 为 SSOT：

- SSOT: `src/IMPL_ROOT/cli/yaml_dsl.py`
- skill 生成入口: `just gen-agent-skill`（注入 marker 内部内容；禁止手改区块内部）
- docs-site 入口: `just gen-docs`（对应 docs 页同样使用 injected blocks）

指引 MUST 明确包含:
- `uv run PROJECT_CLI_NAME yaml-dsl validate <file.yaml>`
- `uv run PROJECT_CLI_NAME yaml-dsl schema validate <file.yaml>`
- `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME yaml-dsl validate <file.yaml>`
- `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME yaml-dsl schema validate <file.yaml>`
- `uv run PROJECT_CLI_NAME yaml-dsl schema path`
- `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME yaml-dsl schema path`
- `# yaml-language-server: $schema=...` 的 header 参考

skill MUST 明确指出 schema path 可通过 `PROJECT_CLI_NAME yaml-dsl schema path` 查询,并提供 header 模板。
skill MUST 明确指出 canonical example 不应固化本机 `.venv/...`、`site-packages/...` 或仓库私有相对路径头部。

#### Scenario: 仓库内用户获取校验指引
- **WHEN** 用户在仓库内工作并请求校验 YAML
- **THEN** skill 必须提供 `uv run PROJECT_CLI_NAME ...` 形式的命令

#### Scenario: 脱离仓库用户获取 CLI 指引
- **WHEN** 用户不在仓库内但需要运行 CLI 校验
- **THEN** skill 必须提供 `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME ...` 形式的命令

#### Scenario: 用户需要配置 YAML LSP
- **WHEN** 用户请求编辑器补全或 schema 头部示例
- **THEN** skill 必须提供 `$schema` header 示例与 schema path 获取方式

#### Scenario: hand-written snippets outside injected blocks are rejected
- **WHEN** 维护者在 `artifacts/skills/scalim-yaml-dsl/SKILL.md` 的 injected block marker 外手写可复制命令片段
- **THEN** `just qa` MUST 失败并提示通过 `just gen-agent-skill` 修复

