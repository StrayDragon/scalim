## ADDED Requirements

### Requirement: LSP server MUST support codeAction and executeCommand
系统 MUST 支持：

- `textDocument/codeAction`
- `workspace/executeCommand`

并且 MUST：

- 通过 `WorkspaceEdit` 应用编辑
- 在执行失败时返回可诊断信息（不得 crash）

#### Scenario: codeAction returns an executable fix
- **GIVEN** 当前文档存在一条可修复的 discovery/diagnostics 问题
- **WHEN** client 请求 codeAction
- **THEN** server MUST 返回可执行的 fix（edit 或 executeCommand）

### Requirement: executeCommand MUST support dumping discovery summary as JSON
系统 MUST 通过 `workspace/executeCommand` 暴露一个可用于排障的 discovery dump command：

- command id MUST 为 `scalim.dumpDiscovery`
- command arguments MUST 至少包含一个 document URI（作为 discovery 的入口）
- 返回值 MUST 为可 JSON 序列化的 discovery 摘要（不得回显 YAML 正文）

discovery 摘要 MUST 至少包含：

- project_root
- scalim_yaml_path（可为空）
- python_roots
- allowed_yaml_roots

#### Scenario: dumpDiscovery returns a JSON-serializable discovery payload
- **GIVEN** client 提供一个已打开文档的 URI
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDiscovery`
- **THEN** server MUST 返回包含 `project_root/scalim_yaml_path/python_roots/allowed_yaml_roots` 的 JSON payload
