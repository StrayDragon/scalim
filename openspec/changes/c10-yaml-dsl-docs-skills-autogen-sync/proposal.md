## Why

YAML DSL 的对外可用性很大程度依赖两类“可复制 reference”：

1) CLI/LSP 命令片段（validate/schema validate/upsert-lsp-comment 等）
2) Schema 字段集合与必填边界（Top-Level fields / definitions）

目前这些内容同时出现在 `docs/doc/yaml-dsl/**` 与 `artifacts/skills/scalim-yaml-dsl/**` 的多个位置，其中部分仍为手工维护；一旦实现迭代（新增参数/调整命令/新增 schema 字段），文档与 skill 很容易发生“局部漂移”，导致：

- 开发者体验：贡献者/agent 不确定哪份文案可信，只能反复跑命令/对照源码
- 库用户体验：按文档写出的命令或 `$schema` 头部不准确，校验/编辑器体验变差
- 可维护性：同一份 reference 在多处重复，review 成本高且容易漏改

本变更的目标是把上述两类 reference 收敛为 **代码/生成物单源**，并通过门禁把“手写片段漂移”变成可回归的失败信号。

## As-Is 调研（当前漂移点与缺口）

### 1) docs/skill 里仍有大量“手写可复制命令片段”

- `docs/doc/yaml-dsl/workflow.md`：包含 workflow validate / schema validate / upsert-lsp-comment 等命令清单（目前无 injected block marker，属于手写片段）
- `docs/doc/yaml-dsl/agent-skill.md`：包含一整段可复制命令清单（目前无 injected block marker）
- `artifacts/skills/scalim-yaml-dsl/SKILL.md`：包含最小命令入口清单（目前无 injected block marker）

目前仓库的 injected blocks 主要用于其它内容（例如 `docs/doc/yaml-dsl/user-guide.md` 的 `yaml-dsl-source-field-extract`、`docs/doc/yaml-dsl/upgrades/index.md` 的 `yaml-dsl-upgrades-index`），尚未覆盖 CLI/LSP reference 的“最小命令片段”。

### 2) schema reference 生成页只覆盖 demand，缺 workflow

- `docs/doc/yaml-dsl/schema-reference.gen.md` 当前只从 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 渲染（`scripts/gen-docs.py::_render_yaml_schema_reference`）
- `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 已存在，但字段参考未进入 docs-site（导致 workflow authoring 的“Top-Level fields/definitions”只能看 schema 源码或 editor）

### 3) CLI docs 摘录与 renderer 已有基础，但覆盖不全

- 录制入口已存在：`packages/scalim-misc/src/scalim_misc/cli_docs.py::build_yaml_dsl_command_docs()`
  - 当前仅列出 `validate` / `schema validate|show|path`，导致 `upsert-lsp-comment` 的“Command Details/full help”缺失
- skill 已生成 `references/generated/cli-lsp-reference.gen.md`，但 docs-site 尚无同源的 CLI reference 页面（且“最小命令入口”仍是多处手写）

## What Changes

- CLI reference 单源化（以 CLI parser 为 SSOT）：
  - 从 `src/scalim/cli/yaml_dsl.py` 的 argparse parser 自动摘录并生成参考页/片段
  - 覆盖并补齐 `yaml-dsl upsert-lsp-comment` 等容易遗漏的子命令

- Schema reference 单源化（以 JSON schema 为 SSOT）：
  - 以 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 与 `.../workflow.gen.json` 为字段集合真相
  - docs-site 的 `schema-reference.gen.md` 生成内容扩展到同时包含 demand/workflow 两套字段参考

- docs-site：禁止手写“可复制命令片段”：
  - 新增 `docs/doc/yaml-dsl/cli-reference.gen.md` 作为完整 CLI/LSP 参考页（生成物，禁止手改）
  - `docs/doc/yaml-dsl/workflow.md` 与 `docs/doc/yaml-dsl/agent-skill.md` 中的命令速查改为 injected blocks（禁止手改区块内部）

- skills：禁止手写“最小命令入口”漂移：
  - `artifacts/skills/scalim-yaml-dsl/SKILL.md` 的最小命令清单改为 injected blocks（区块外仍保持手工 routing-first）
  - skill 生成的 `references/generated/cli-lsp-reference.gen.md` 与 docs-site 使用同源摘录，避免出现“同命令两套文案”

- 治理门禁（强约束）：
  - 增加严格检查：若目标文件缺少 marker 或 marker 外出现手写命令片段，则 `just qa` 必须失败并给出修复指引（`just gen-docs` / `just gen-agent-skill`）
  - 该门禁默认只覆盖少量目标文件（`workflow.md`、`agent-skill.md`、`SKILL.md`），避免误伤其它叙事性文档；并且只匹配高置信度命令前缀（例如 `uv run scalim-cli yaml-dsl`、`uvx --from "scalim[cli]" scalim-cli yaml-dsl`）。

## Capabilities

### New Capabilities
- `yaml-dsl-docs-skills-autogen-sync`: YAML DSL 的 CLI/LSP + schema reference 从实现/生成物自动同步到 docs-site 与 skill，并通过治理门禁禁止手写漂移

### Modified Capabilities
- `yaml-dsl-agent-guidance`: skill 的 CLI/LSP guidance 从“手写片段”升级为“注入的受控片段”（仍保持 skill 本体手工 routing-first）

## Impact

- SSOT（事实来源）：
  - CLI：`src/scalim/cli/yaml_dsl.py`
  - schema：`src/scalim/dsl/by_yaml/schema/demand.gen.json`、`src/scalim/dsl/by_yaml/schema/workflow.gen.json`

- 生成入口与门禁（不手改 `.gen.*` 与 injected blocks）：
  - docs-site：`scripts/gen-docs.py` / `just gen-docs`；漂移门禁：`just docs-drift-check`（`just qa` 覆盖）
  - skill：`scripts/gen-agent-skill.py` / `just gen-agent-skill`；校验：`just validate-agent-skill`（`just qa` 覆盖）
  - 新增治理检查（目标：纳入 `quick-check-only-py`，因此进入 `just qa`）

- 受影响输出（生成物/注入区块）：
  - 新增：`docs/doc/yaml-dsl/cli-reference.gen.md`（生成物）
  - 更新：`docs/doc/yaml-dsl/schema-reference.gen.md`（生成物，扩展 workflow 部分）
  - 注入区块（禁止手改区块内部）：
    - `docs/doc/yaml-dsl/workflow.md`
    - `docs/doc/yaml-dsl/agent-skill.md`
    - `artifacts/skills/scalim-yaml-dsl/SKILL.md`
