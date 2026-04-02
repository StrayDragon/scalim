## Why

在 VSCode extension MVP 可稳定拉起 server 后，用户体验的关键提升点在于：

- 让 LSP server 的 code actions（Quick Fix）以更自然的 VSCode “Actions” 形态出现并可诊断
- 提供清晰的运行状态与排障入口（当前使用的 venv、server 版本、discovery 结果、最近一次启动错误等）

这能显著降低 YAML DSL 的使用门槛，并减少“配置/环境问题”造成的支持成本。

## What Changes

- 在 VSCode extension 中增强 actions 与 UX：
  - 将 server 的 `codeAction/executeCommand` 能力完整映射为 VSCode Quick Fix（必要时增加更友好的文案/分组）
  - 增加常用命令：重启 server、打开日志、显示当前 discovery 配置、打开/创建 `scalim.yaml`
  - 增加状态栏/输出面板信息（server 运行状态、版本、当前 workspace 的 project root）
- 扩展侧不得复制 YAML DSL 语义；所有诊断与修复建议必须来自 server/shared core。

非目标（本变更不做）：
- 引入复杂 UI（WebView 配置面板等）
- 扩展 scope 外的编辑器支持（Neovim/Zed/JetBrains 走 `yaml-dsl-lsp-editor-integration-guides`）

## Capabilities

### New Capabilities

### Modified Capabilities
- `yaml-dsl-vscode-extension`: 补充并实现 actions/UX 相关 requirements，使 VSCode “Actions” 能稳定呈现 YAML DSL 的 Quick Fix，并提供一键排障入口。

## Impact

- 影响代码/资产：
  - VSCode extension 工程：新增 commands、状态栏展示、actions glue code
  - `openspec/specs/yaml-dsl-vscode-extension/spec.md`：扩展 requirements（actions/诊断/排障）
- 依赖关系：
  - 需要 server 侧已具备标准 LSP code actions（依赖 `yaml-dsl-lsp-server-code-actions`）

