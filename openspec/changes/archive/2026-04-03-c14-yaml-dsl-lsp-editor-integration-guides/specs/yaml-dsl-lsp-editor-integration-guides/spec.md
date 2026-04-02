## ADDED Requirements

### Requirement: Docs site MUST provide editor integration guides for YAML DSL LSP server
系统 MUST 在 docs-site 中提供多编辑器接入指南，至少覆盖：

- Neovim
- Zed editor
- JetBrains（LSP Support 插件）

每个指南 MUST 包含：

- server 启动命令（stdio）
- YAML 文件匹配规则/启用方式
- workspace root 与 project discovery 的说明

#### Scenario: user can copy a minimal config to start the server
- **WHEN** 用户按文档复制最小配置到编辑器
- **THEN** 该编辑器 MUST 能拉起 server 并收到 diagnostics

### Requirement: Docs MUST clarify schema vs LSP responsibility boundaries
文档 MUST 明确：

- YAML schema 插件负责结构校验/补全
- LSP server 负责语义 diagnostics + Python 引用跳转/hover/补全（以及 actions）

#### Scenario: user understands which tool provides which validation
- **WHEN** 用户阅读集成指南
- **THEN** 文档 MUST 明确指出 schema 与 LSP 的职责边界

