## ADDED Requirements

### Requirement: VSCode extension MUST surface LSP code actions as Quick Fix and provide one-click troubleshooting commands

系统 MUST 要求 VSCode extension 将 YAML DSL LSP server 的标准 LSP code actions 映射为 VSCode Quick Fix，并提供一键排障入口：

- Quick Fix MUST 直接来源于 server 的 `codeAction/executeCommand`（extension 不得复制语义规则）
- extension MUST 提供命令：重启 server、打开日志、显示当前 discovery 摘要、打开/创建 `scalim.yaml`
- extension SHOULD 提供状态栏信息（server 运行状态与版本）

#### Scenario: a Quick Fix can create scalim.yaml from the editor UI
- **GIVEN** 当前 YAML 无法发现 `scalim.yaml` 且 server 提供对应 Quick Fix
- **WHEN** 用户在 VSCode 中选择 Quick Fix
- **THEN** extension MUST 执行对应 command 并应用 `WorkspaceEdit`
- **AND** 用户 MUST 能在日志中看到可诊断信息（包含 discovery 摘要）
