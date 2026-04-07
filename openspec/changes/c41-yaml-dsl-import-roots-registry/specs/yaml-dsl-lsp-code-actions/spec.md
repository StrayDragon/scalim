# yaml-dsl-lsp-code-actions Specification

## MODIFIED Requirements

### Requirement: Command ids and arguments MUST be stable for editor integration
系统 MUST 为 v1 Quick Fix 提供稳定的 command id 与参数协议（供 VSCode/Neovim/Zed/JetBrains 等 client 复用）。

v1 command id（不区分 client）至少包含：

- `scalim.yaml.createMinimal`：`[document_uri]`
- `scalim.yaml.addImportRoots`：`[document_uri, mode]`，其中 `mode` 为 `minimal|wide`
- `scalim.yaml.addPythonRoots`：`[document_uri, mode]`，其中 `mode` 为 `minimal|wide`
- `scalim.python.explainResolutionFailure`：`[document_uri, reference]`

#### Scenario: user can invoke a documented quick fix command id from any client
- **GIVEN** 某 LSP client 支持 `workspace/executeCommand`
- **WHEN** client 使用文档中列出的 command id 与参数协议调用 Quick Fix
- **THEN** server MUST 接受该请求并返回可诊断的结果（成功时应用 edit；失败时返回 explain-only payload）

