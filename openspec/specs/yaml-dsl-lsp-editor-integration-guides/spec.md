# yaml-dsl-lsp-editor-integration-guides Specification

## Purpose
提供一套可复制、可审计、可排障的多编辑器接入指南，降低 YAML DSL LSP server 在 Neovim / Zed / JetBrains 等生态中的接入成本，并明确 schema 与 LSP 的职责边界。

## Requirements
### Requirement: Docs site MUST provide editor integration guides for YAML DSL LSP server
系统 MUST 在 docs-site 中提供多编辑器接入指南，至少覆盖：

- Neovim
- Zed editor
- JetBrains（LSP Support 插件）

每个指南 MUST 以“可复制、无需预安装二进制”为默认目标，并至少提供两种等价启动模式（按推荐优先级排序）：

1) **Ephemeral（默认推荐）**：通过 `uvx` 启动 `scalim-yaml-dsl-lsp`  
2) **Installed（可选）**：通过已安装的 `scalim-yaml-dsl-lsp` 二进制启动

每个指南 MUST 包含：

- server 启动命令（stdio）
  - MUST 给出 `uvx scalim-yaml-dsl-lsp serve ...` 的最小启动示例（默认推荐）
  - MUST 给出 `scalim-yaml-dsl-lsp serve ...` 的等价替代示例（installed）
- YAML 文件匹配规则/启用方式
- workspace root 与 project discovery 的说明

#### Scenario: user can copy a minimal config to start the server
- **GIVEN** 用户机器已安装 `uv`（`uvx` 可用），且未预安装 `scalim-yaml-dsl-lsp` 二进制
- **WHEN** 用户按文档复制 uvx 版最小配置到编辑器
- **THEN** 该编辑器 MUST 能通过 `uvx` 拉起 server 并收到 diagnostics

### Requirement: Docs MUST clarify schema vs LSP responsibility boundaries
文档 MUST 明确：

- YAML schema 插件负责结构校验/补全
- LSP server 负责语义 diagnostics + Python 引用跳转/hover/补全（以及 actions）

#### Scenario: user understands which tool provides which validation
- **WHEN** 用户阅读集成指南
- **THEN** 文档 MUST 明确指出 schema 与 LSP 的职责边界
