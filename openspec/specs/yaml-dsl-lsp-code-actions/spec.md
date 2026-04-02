# yaml-dsl-lsp-code-actions Specification

## Purpose
定义 YAML DSL LSP 的 Quick Fix（`textDocument/codeAction` + `workspace/executeCommand`）能力集合与安全约束，确保：

- actions 由 shared core 的 diagnostics/discovery 驱动（避免在 server 层复制 DSL 语义）
- edits 可撤销、可审计（通过 `WorkspaceEdit`）
- 纯静态无副作用（不得执行用户代码）
- edits 仅作用于 workspace 内文件（越界/不可写时降级为 explain-only）

## Requirements
### Requirement: Server MUST expose code actions driven by shared core diagnostics and discovery
系统 MUST 暴露 YAML DSL 的 Quick Fix（`textDocument/codeAction`）能力，且 actions 的触发依据 MUST 来自 shared core 输出：

- diagnostics（errors/warnings + range + path）
- project discovery 摘要（project_root/scalim_yaml_path/python_roots/allowed_yaml_roots）
- Python resolution warnings（如可获得）

actions MUST 满足：

- MUST 通过 `WorkspaceEdit` 应用（可撤销、可审计）
- MUST 静态无副作用（不得执行用户代码）
- MUST 不在 server 层复制 DSL 语义规则

#### Scenario: missing scalim.yaml yields a create action
- **GIVEN** shared core discovery 表明 `scalim_yaml_path` 为空
- **WHEN** client 请求 codeAction
- **THEN** server MUST 返回至少一个 “Create minimal scalim.yaml” action

### Requirement: Actions MUST be safe and workspace-scoped
系统 MUST 只对 workspace 内文件提供可写 edits：

- 若目标文件不可写或不在 workspace，action MUST 降级为 explain-only（不附带 edit）

#### Scenario: non-workspace target yields no edit
- **GIVEN** 某 action 需要写入 workspace 外文件
- **WHEN** server 构造该 action
- **THEN** server MUST 不返回 `WorkspaceEdit`

### Requirement: Command ids and arguments MUST be stable for editor integration
系统 MUST 为 v1 Quick Fix 提供稳定的 command id 与参数协议（供 VSCode/Neovim/Zed/JetBrains 等 client 复用）。

v1 command id（不区分 client）至少包含：

- `scalim.yaml.createMinimal`：`[document_uri]`
- `scalim.yaml.addImportAllowedRoots`：`[document_uri, mode]`，其中 `mode` 为 `minimal|wide`
- `scalim.yaml.addPythonRoots`：`[document_uri, mode]`，其中 `mode` 为 `minimal|wide`
- `scalim.python.explainResolutionFailure`：`[document_uri, reference]`

#### Scenario: user can invoke a documented quick fix command id from any client
- **GIVEN** 某 LSP client 支持 `workspace/executeCommand`
- **WHEN** client 使用文档中列出的 command id 与参数协议调用 Quick Fix
- **THEN** server MUST 接受该请求并返回可诊断的结果（成功时应用 edit；失败时返回 explain-only payload）
