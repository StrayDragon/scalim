# yaml-dsl-agent-guidance (delta) Specification

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
- `uvx PROJECT_CLI_NAME yaml-dsl validate <file.yaml>`
- `uvx PROJECT_CLI_NAME yaml-dsl schema validate <file.yaml>`
- `uv run PROJECT_CLI_NAME yaml-dsl schema path`
- `uvx PROJECT_CLI_NAME yaml-dsl schema path`
- `uv run PROJECT_CLI_NAME yaml-dsl lint <paths...>`
- `uvx PROJECT_CLI_NAME yaml-dsl lint <paths...>`
- `uv run PROJECT_CLI_NAME yaml-dsl format <paths...>`
- `uvx PROJECT_CLI_NAME yaml-dsl format <paths...>`
- `# yaml-language-server: $schema=...` 的 header 参考

skill MUST 明确指出 schema path 可通过 `PROJECT_CLI_NAME yaml-dsl schema path` 查询,并提供 header 模板。
skill MUST 明确指出 canonical example 不应固化本机 `.venv/...`、`site-packages/...` 或仓库私有相对路径头部。

#### Scenario: 仓库内用户获取校验指引
- **WHEN** 用户在仓库内工作并请求校验 YAML
- **THEN** skill 必须提供 `uv run PROJECT_CLI_NAME ...` 形式的命令

#### Scenario: 脱离仓库用户获取 CLI 指引
- **WHEN** 用户不在仓库内但需要运行 CLI 校验
- **THEN** skill 必须提供 `uvx PROJECT_CLI_NAME ...` 形式的命令

#### Scenario: 用户需要配置 YAML LSP
- **WHEN** 用户请求编辑器补全或 schema 头部示例
- **THEN** skill 必须提供 `$schema` header 示例与 schema path 获取方式

#### Scenario: hand-written snippets outside injected blocks are rejected
- **WHEN** 维护者在 `agentdev/skills/scalim-yaml-dsl/SKILL.md` 的 injected block marker 外手写可复制命令片段
- **THEN** `just qa` MUST 失败并提示通过 `just gen-agent-skill` 修复

## ADDED Requirements

### Requirement: `scalim-yaml-dsl` skill MUST recommend plain scalars and multiline `call_by` authoring
当 skill/agent 输出或改写 YAML DSL 时，系统 MUST 将“可读性优先 + 工具保证一致性”作为默认风格：

- 对 `loader/call_by/compute/retry.should_retry` 这类 string 值：
  - 在语义等价且不会触发 YAML 隐式类型的前提下，MUST 优先使用 plain scalar（不写无意义引号）
  - 当 `call_by` 很长或需要注释时，MUST 推荐使用 YAML block scalar（`|`）并按多行函数调用排版
- skill MUST 明确指出：团队可通过 `PROJECT_CLI_NAME yaml-dsl format` 统一风格，并避免手工维护差异

#### Scenario: skill prefers plain scalar for simple compute and block scalar for long call_by
- **WHEN** 用户请求生成/重构包含 `compute` 与长 `call_by` 的 YAML
- **THEN** skill MUST 输出 `compute: order_id` 这类 plain scalar 写法
- **AND** 长 `call_by` MUST 以 `call_by: |` 的多行形式给出（允许行尾注释与可选 trailing comma）

