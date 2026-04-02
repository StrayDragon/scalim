## Context

在完成 server MVP（diagnostics + 跳转/hover/补全）后，用户仍会被“工程发现失败/roots 不完整/imports 越界”等问题阻塞。此类问题具有共同特征：

- 需要编辑 `scalim.yaml` 或小范围文本修复
- 修复步骤可标准化
- 修复后可立即改善 diagnostics 与跳转体验

LSP 的 `codeAction` + `executeCommand` 允许把这些修复变成可撤销、可审计的一键 Quick Fix，并被 VSCode/Neovim/Zed/JetBrains 等复用。

## Goals / Non-Goals

**Goals:**

- server 支持 `textDocument/codeAction` 与 `workspace/executeCommand`
- actions MUST 由 shared core 输出驱动（diagnostics/warnings/discovery/Python resolution warnings），避免在 server 层复制 DSL 语义
- 通过 `WorkspaceEdit` 应用修改（可撤销、可审计）
- 任何 action 必须静态无副作用（仅文本编辑；不得执行用户代码）

**Non-Goals:**

- 在 server 侧引入复杂 UI/交互式向导
- 在扩展侧复制语义（扩展仅展示与 glue；语义来自 server/core）

## Decisions

1) **actions 以稳定 command id + 参数协议表达**

- 为每个 Quick Fix 定义稳定的 `command`（例如 `scalim.yaml.createMinimal`）
- `codeAction` 返回 `Command`/`WorkspaceEdit`，需要参数时通过 `executeCommand` 执行

2) **最小 actions 集合（v1）**

优先实现“高频且确定性强”的修复：

- 缺失 `scalim.yaml` → Create minimal `scalim.yaml`
- imports 越界（allowed roots 不包含需要目录）→ Add `yaml_dsl.import_allowed_roots`
- python_roots 缺失/不合理 → Add `yaml_dsl.editor.python_roots`（仅在不越界约束可满足时；否则提供 explain-only）
- Python 引用不可解析 → Explain resolution failure（不强行改写引用）

3) **安全边界：仅编辑工作区文件**

- edit MUST 仅作用于当前 workspace 内的文件
- 如果目标文件不可写/路径不在 workspace，action MUST 降级为 explain-only（不提供 edit）

4) **dump discovery：通过 executeCommand 导出 JSON**

- 增加一个 debug command（`workspace/executeCommand`）：用于导出当前 workspace 的 discovery 摘要（JSON）
- 该能力与 `scalim-yaml-dsl-lsp dump-discovery` CLI 子命令保持字段口径一致，便于 issue 排障

5) **roots 建议策略：推导为主 + 两档 action**

- server 允许基于 workspace 常见结构推导建议 roots（仅包含“确实存在”的目录）
- 对同一问题提供两档 Quick Fix（用户通过选择 action 完成确认）：
  - 最小修复（仅修复当前报错所需的 root）
  - 更宽松（例如将 `import_allowed_roots` 扩展为 `.`）

## Risks / Trade-offs

- [不同 client 对 WorkspaceEdit 支持差异] → v1 采用最基础 edit 结构；补充集成测试与说明文档
- [对 project discovery 约束不了解导致错误建议] → 以 shared core 输出为 SSOT；对无法确定的情况提供 explain-only

## Migration Plan

- 新增 code actions 不改变运行时语义；仅增加编辑器可选能力。

## Open Questions
（无；v1 采用 executeCommand dump + 推导为主的两档 Quick Fix）
