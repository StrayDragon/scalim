# yaml-dsl-lsp-editor-integration-guides (delta) Specification

## ADDED Requirements

### Requirement: Integration guides MUST document a multiline `call_by` authoring style that preserves navigation
docs-site 的 editor integration guides MUST 明确推荐一种“可读且可跳转”的 `call_by` 写法，并满足：

- 当 `call_by` 参数较多时，文档 MUST 推荐使用 YAML block scalar（`|`）将其拆为多行
- 文档 MUST 明确允许在参数行使用 Python 风格 `#` 注释（不在 string literal 内）
- 文档 MUST 明确：参数行尾逗号为可选（trailing comma optional）
- 文档 MUST 明确：在该写法下，head reference 与 kwargs 右侧 field-id token 仍应支持 hover/definition/completion（失败时应提示排障路径，而不是静默失效）

#### Scenario: user can follow the guide to write a multiline call_by without losing go-to-definition
- **WHEN** 用户按文档将 `call_by` 改写为 block scalar 多行形式并在编辑器中触发 go-to-definition
- **THEN** 该编辑器 MUST 仍能对 head reference 提供跳转（或给出可诊断的 warnings）

