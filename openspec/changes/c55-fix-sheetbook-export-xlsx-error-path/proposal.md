## Why

`xlsx_memory`（内部以 `sheetbook` 资源实现）在 workflow 运行期准备 `export_xlsx.path`（版本化输出 root、version dir、manifest 等）时，若遇到 `OSError` / `FileExistsError` 等异常，需要给出**可操作**且**可定位**的错误路径（`ScalimWorkflowConfigError.path`）。

目前该路径在“内部资源类型（sheetbook）”与“用户 authoring surface（books.kind=xlsx_memory + export_xlsx.path）”之间存在潜在歧义空间：即便底层实现仍正确，错误定位与报错语义也应稳定地指向用户配置处，避免排障时在 books/sheetbook 两套概念之间来回跳转。

## What Changes

- 明确并固化 `sheetbook`（xlsx_memory）导出路径相关的错误定位规则：`ScalimWorkflowConfigError.path` 必须指向用户配置键（`workflow.resources.books.<book_id>.export_xlsx.path`）。
- 必要时在错误 message 中补充内部资源类型提示（例如 `resource_type=sheetbook`），以便在 IR/事件流排障时建立映射。
- 增加回归测试，确保上述 path 规则不因重构漂移。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `workflow-sheetbook-resources`: `xlsx_memory` 的导出（`export_xlsx.path`）相关错误必须提供可操作的配置定位路径，并与 authoring surface（books）保持一致。

## Impact

- 受影响代码：`src/scalim/workflow/resource_defs.py`（以及可能的 `workflow` 错误包装/提示信息）。
- 行为影响：错误信息/`path` 字段更稳定、更一致（对外属于 UX 改进；可能影响依赖错误字符串的测试）。
- 对外 API：无功能性变更；仅增强错误诊断与规范一致性。
