## ADDED Requirements

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

