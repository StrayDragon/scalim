## Why

仅靠 diagnostics + 跳转，用户仍然会频繁卡在“配置缺失/工程发现失败/roots 不完整”这类问题上，需要手工排障与修复，成本高且不稳定。

LSP 标准的 `codeAction/executeCommand` 可以把这些修复变成可撤销、可审计的一键 Quick Fix：

- VSCode 能自然呈现 “Actions / Quick Fix”
- Neovim/Zed/JetBrains 等同样可复用（只要 client 支持 code actions）

## What Changes

### P0（必须）
- server 支持：
  - `textDocument/codeAction`
  - `workspace/executeCommand`
- Quick Fix 的基本约束：
  - MUST 复用 shared core 的输出作为触发依据（diagnostics/warnings/discovery/Python resolution warnings），避免在 server 层复制 DSL 语义规则
  - MUST 通过 `WorkspaceEdit` 应用（可撤销、可审计）
  - MUST 静态无副作用（仅文件写入/文本编辑；不得执行用户代码）

### v1 Quick Fix 候选集合（建议从小做强）
- `scalim.yaml` 缺失：
  - 提供 “Create minimal scalim.yaml” action
- `python_roots` 缺失/不合理：
  - 提供 “Add yaml_dsl.editor.python_roots” action（按常用目录给出建议）
- YAML imports 越界（allowed roots 不包含需要目录）：
  - 提供 “Add yaml_dsl.import_allowed_roots” action
- Python 引用不可解析：
  - 提供 “Explain resolution failure” 的可诊断提示（必要时可生成建议项，但不强行改写引用字符串）

### P1（建议）
- 将 actions 分组与命名做成稳定 contract（便于 VSCode UX 与文档引用）
- 提供一个 debug command 输出 discovery 摘要（便于用户在 issue 中直接粘贴）

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-code-actions`: YAML DSL LSP 的 Quick Fix（codeAction/executeCommand）能力集合与约束（静态、可撤销、由 core 诊断驱动）。

### Modified Capabilities
- `yaml-dsl-lsp-server`: 要求 server 能暴露并执行 code actions，且不得在 server 层复制语义规则。

## Impact

- 影响代码/资产（预期）：
  - `packages/scalim-yaml-dsl-lsp/`：server 增加 codeAction/executeCommand handlers
  - `tests/`：新增 actions 行为的回归用例（WorkspaceEdit 结果断言）
