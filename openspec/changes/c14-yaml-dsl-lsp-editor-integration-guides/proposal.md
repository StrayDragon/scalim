## Why

即便 LSP server 本身可运行，多编辑器接入依然会因为配置口径与排障入口不清晰而反复踩坑，典型问题包括：

- 启动命令/工作区 root/文件匹配规则差异
- discovery 配置（`scalim.yaml`、`python_roots`、`allowed_yaml_roots`）不透明导致“跳转不工作”
- schema（YAML 结构体验）与 LSP（语义体验）协作方式不明确

需要一套“可复制 + 可审计 + 可排障”的集成指南，降低 Neovim/Zed/JetBrains 等生态的接入成本。

## What Changes

### P0（必须）
- 在 docs-site 中提供多编辑器接入指南（至少覆盖）：
  - Neovim（LSP client 启动命令 + filetype/glob 规则）
  - Zed editor（language server 配置）
  - JetBrains（LSP Support 插件配置）
- 明确 schema 与 LSP 的协作口径：
  - 不替换 YAML schema 插件（例如 VSCode 的 `redhat.vscode-yaml`）
  - schema 负责结构校验/补全；LSP 负责语义 diagnostics + Python 引用跳转
- 提供排障入口：
  - 如何查看 server 日志
  - discovery 摘要（project_root/scalim_yaml_path/python_roots/allowed_yaml_roots）

### P1（建议）
- 将“可复制命令片段/配置片段”纳入 docs 治理：
  - 避免在多个文档里手写启动命令，防止与实现漂移
  - 必要时通过 `just gen-docs` 的 injected blocks 统一生成

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-editor-integration-guides`: 多编辑器接入指南与排障手册（可复制配置 + discovery 口径）。

### Modified Capabilities
- `yaml-dsl-lsp-serve`: 对 serve contract 增补“可诊断输出”要求（便于用户自助排障）。

## Impact

- 影响代码/资产（预期）：
  - `docs/doc/yaml-dsl/`：新增/扩展 LSP/IDE 集成文档页
  - 若引入 injected blocks：需遵守 docs governance，并通过 `just gen-docs` 维护

