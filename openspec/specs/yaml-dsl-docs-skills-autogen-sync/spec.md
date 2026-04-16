# yaml-dsl-docs-skills-autogen-sync Specification

## Purpose
TBD - created by archiving change c30-yaml-dsl-docs-skills-autogen-sync. Update Purpose after archive.
## Requirements
### Requirement: YAML DSL CLI reference MUST be generated from CLI parser and shared by docs and skill
系统 MUST 以 `src/IMPL_ROOT/cli/yaml_dsl.py` 的 argparse parser 为命令真相，并将其输出作为 docs-site 与 `scalim-yaml-dsl` skill 的共享 reference 来源，禁止手工维护重复文案。

系统 MUST 至少覆盖并可从生成物中发现以下子命令与其 usage/help：

- `yaml-dsl validate`
- `yaml-dsl schema validate/show/path`
- `yaml-dsl upsert-lsp-comment`

#### Scenario: docs-site provides a generated CLI reference page
- **WHEN** 维护者运行 `just gen-docs`
- **THEN** MUST 生成 `docs/doc/yaml-dsl/cli-reference.gen.md`
- **AND** 该页面 MUST 包含 `yaml-dsl upsert-lsp-comment` 的 usage/help（不允许缺失）

#### Scenario: skill provides a generated CLI/LSP reference
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** MUST 生成 `agentdev/skills/scalim-yaml-dsl/references/generated/cli-lsp-reference.gen.md`
- **AND** 该 reference MUST 覆盖 `yaml-dsl upsert-lsp-comment`（不允许缺失）

### Requirement: Copyable CLI/LSP snippets MUST be injected and hand-written snippets MUST be rejected
系统 MUST 将“可复制的命令片段（CLI/LSP）”收敛为 injected blocks，并禁止在 marker 外手写这些片段，以避免与实现漂移。

至少 MUST 覆盖以下文件：

- `docs/doc/yaml-dsl/workflow.md`
- `docs/doc/yaml-dsl/agent-skill.md`
- `agentdev/skills/scalim-yaml-dsl/SKILL.md`

#### Scenario: required markers exist
- **WHEN** 维护者查看上述文件
- **THEN** 每个文件 MUST 包含对应的 `BEGIN/END AUTOGEN:*` marker

#### Scenario: hand-written snippets outside markers fail fast
- **WHEN** 维护者在 marker 外写入 `uv run PROJECT_CLI_NAME yaml-dsl ...` 或 `uvx PROJECT_CLI_NAME yaml-dsl ...` 的命令片段
- **THEN** `just qa` MUST 失败
- **AND** 错误信息 MUST 提示通过 `just gen-docs` / `just gen-agent-skill` 修复

### Requirement: docs schema reference MUST include demand and workflow schemas
系统 MUST 以 `src/IMPL_ROOT/dsl/yaml_dsl/schema/demand.gen.json` 与 `src/IMPL_ROOT/dsl/yaml_dsl/schema/workflow.gen.json` 为 schema 字段集合真相，并在 docs-site 的 schema reference 页中同时呈现 demand/workflow 两套字段参考（Top-Level Fields + Definitions）。

#### Scenario: schema reference contains workflow fields
- **WHEN** 维护者运行 `just gen-docs`
- **THEN** `docs/doc/yaml-dsl/schema-reference.gen.md` MUST 包含 workflow schema 的 Top-Level Fields/Definitions（不允许仅包含 demand）

### Requirement: QA MUST gate docs/skill sync drift for injected snippets
系统 MUST 提供一个可回归的门禁，用于在 docs/skill 中拦截“可复制片段漂移/遗漏 marker”：

- marker 缺失 MUST fail-fast
- marker 外出现手写命令片段 MUST fail-fast
- 失败信息 MUST 给出明确修复入口（`just gen-docs` / `just gen-agent-skill`）

#### Scenario: QA fails when a required marker is missing
- **WHEN** 任一目标文件缺少 `BEGIN/END AUTOGEN:*` marker
- **THEN** `just qa` MUST 失败并提示补齐 marker 与运行生成入口
