## Why

在当前机制下，`scalim.yaml` 同时承载了：

- imports 的路径治理（`import_aliases` / `import_allowed_roots`）
- 编辑器/LSP 的 project discovery（`python_roots` / `kind_overrides`）
- CLI runner 的运行期默认值（`yaml_dsl.runner.*`，尤其是 allowlist）

这会引发两个长期摩擦：

1. **认知误导**：用户看到项目根的 `scalim.yaml`，很自然会以为 `scalim.dsl.by_yaml.run(...)` 也会读取其中的 runner 配置；但实际上 runner 段仅对 CLI 生效，Python 入口仍要求显式 `RunOptions.allowed_modules/allowed_functions`。这导致“看起来配置了但跑不起来”的错觉。
2. **双入口双维护**：同一份 allowlist / 并行度 / template sandbox 默认值，可能需要分别维护在 CLI flags 与 Python `RunOptions` 里；团队越大越容易出现漂移（本地 CLI 能跑、线上 Python 不能跑，或反之）。

我们希望通过**明确只保留一个执行入口（Python）**，把 `scalim.yaml` 收敛为“项目级 authoring/tooling 配置”，降低误会与治理成本，同时保持 imports 与 LSP 的能力不变。

## What Changes

- **BREAKING**：`scalim.yaml` 中的 `yaml_dsl.editor` 重命名为 `yaml_dsl.lsp`，用于承载 LSP/编辑器 project discovery 配置（`python_roots` / `kind_overrides`）。
- **BREAKING**：移除 `scalim.yaml yaml_dsl.runner` 整段（`allowed_modules/allowed_functions/allowed_yaml_roots/template_sandbox/parallel_mode/max_workers` 等），以及对应的 `scalim.yaml` JSON Schema 定义。
- **BREAKING**：移除 CLI 执行入口：
  - `scalim-cli yaml-dsl run <demand.yaml>`
  - `scalim-cli yaml-dsl workflow run <workflow.yaml>`
- CLI 保留“工具/校验”定位：`validate`、`schema *`、`upsert-lsp-comment` 等（不执行 YAML）。
- 文档与示例统一口径：
  - `scalim.yaml` 仅用于 imports + LSP/discovery（tooling）
  - 运行期策略（allowlist、并行、模板 sandbox 等）仅由 Python `RunOptions` 装配
- 提供明确的迁移说明：如何从 CLI runner 迁移到 Python wrapper（含最小示例），以及如何从 `yaml_dsl.editor` 迁移到 `yaml_dsl.lsp`。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-cli-runner`: 移除 CLI 执行子命令（demand/workflow run），并提供迁移路径到 Python 运行入口。
- `yaml-dsl-project-config-schema`: 更新 `scalim.yaml` schema（移除 `yaml_dsl.runner`，并将 `yaml_dsl.editor` 更名为 `yaml_dsl.lsp`）。
- `yaml-dsl-editor-project-discovery`: discovery 配置键从 `yaml_dsl.editor.*` 切换为 `yaml_dsl.lsp.*`，保持 nearest-wins 语义不变。
- `yaml-dsl-lsp-code-actions`: Quick Fix（补 python roots 等）写入的配置路径更新为 `yaml_dsl.lsp.*`。

## Impact

- 受影响的代码/文档区域：
  - `src/scalim/cli/yaml_dsl.py`：删除 run 子命令与 runner defaults 读取逻辑（仍保留 validate/schema 工具链）。
  - `src/scalim/dsl/by_yaml/_internal/config_parsing/project_config.py`：`scalim.yaml` 解析从 `editor/runner` 收敛为 `lsp`（imports 相关保持）。
  - `src/scalim/dsl/by_yaml/schema_dsl/models/scalim_yaml.py`：更新 schema DSL，重新生成 `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json`（生成物禁止手改）。
  - `packages/scalim-yaml-dsl-lsp/**`：project discovery 与 code actions 读取/写入的配置路径调整。
  - `docs/doc/yaml-dsl/**`、`artifacts/skills/scalim-yaml-dsl/**`：清理 CLI run 与 `yaml_dsl.runner` 相关内容，统一到 Python `RunOptions` 的运行说明。
- SSOT / 生成物治理：
  - SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`、`openspec/specs/**/spec.md`、`docs/doc/**`。
  - 生成物：任何包含 `.gen.` 的文件（例如 `src/scalim/dsl/by_yaml/schema/*.gen.json`）禁止手改；需要通过对应生成入口（例如 `just gen-yaml-dsl-schema` / `just gen-docs`）刷新。
