## Context

Workflow runtime 在准备输出资源（包括 `xlsx_memory` 的最终 `export_xlsx`）时，会对 output root 做布局初始化与 version dir 创建，并在异常时抛出 `ScalimWorkflowConfigError(message, path=...)`。

对于 `xlsx_memory`，内部实现以 `sheetbook` 资源承载 typed rows 与最终导出；但用户的 authoring surface 仍以 `workflow.resources.books.<book_id>.export_xlsx.path` 表达。这会使“内部资源概念”与“用户配置路径”在错误定位上产生潜在认知落差。

## Goals / Non-Goals

**Goals:**
- 固化并测试：`xlsx_memory` 导出相关的 `ScalimWorkflowConfigError.path` 必须指向用户配置键（books.export_xlsx.path），保证错误定位可操作。
- 在不破坏现有错误处理边界的前提下，必要时补充错误 message 的上下文提示，便于 IR/事件排障（例如指出内部资源类型为 sheetbook）。
- 变更仅触及手工维护代码与测试，避免任何生成物/注入区块改动；门禁由 `just qa` 与回归测试兜底。

**Non-Goals:**
- 不重构 workflow 资源模型（不改变 IR 中 `resource_type` 的表达，也不改变 YAML authoring surface）。
- 不在本变更内调整 output root/versioned outputs 的协议或目录布局。
- 不引入新的错误类型层级（保持使用 `ScalimWorkflowConfigError`）。

## Decisions

- **以 authoring surface 为准**：当异常来源可映射到 YAML 配置键时，优先让 `path` 指向 `workflow.resources.books.<book_id>.export_xlsx.path`，避免暴露内部实现细节给最终用户。
- **内部提示放在 message**：如需在排障中暴露 `sheetbook` 语义，放在 `message` 的附加信息中（例如 “(resource_type=sheetbook)”），而不是改变 `path` 结构。
- **回归测试锁定语义**：添加针对典型异常（例如 `PermissionError` / `FileExistsError`）的测试，断言 `ScalimWorkflowConfigError.path` 的精确值，防止后续重构漂移。

## Risks / Trade-offs

- [风险] 依赖错误字符串/路径的测试会因路径收敛而需要更新 → [缓解] 将断言集中在少数“错误定位语义测试”中，其他用例只匹配关键片段。
- [风险] message 中增加内部提示可能被视为噪音 → [缓解] 仅在确有歧义时追加，保持默认消息简洁。
