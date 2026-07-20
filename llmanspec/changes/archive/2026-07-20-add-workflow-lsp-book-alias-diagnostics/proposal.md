# Change: add-workflow-lsp-book-alias-diagnostics

## Why

c999 硬删 `xlsx_file`/`xlsx_memory` 后，demand LSP 已通过 `ConfigValidator` 给出可复制迁移文案；workflow LSP 仍是 schema-only，旧别名只报 `Unknown field` / generic schema error，编辑体验不一致。

## What Changes

- 在保持「不 compile/run workflow」边界的前提下，为 workflow diagnostics 增加**静态** books 别名迁移诊断（与 demand 同文案）。
- 修正 `yaml-dsl-lsp-server` 中 r564：schema-only 仍是基线，但允许 `workflow.resources.books` 的静态迁移诊断。
- 更新 LSP contract / editor-semantics 期望：workflow 旧别名诊断 MUST 含迁移提示。

## Capabilities

- `yaml-dsl-lsp-server`

## Impact

- BREAKING for editor UX expectations only if clients asserted exact workflow diagnostic messages for removed book keys（现将增加 migration message；schema/unknown 诊断可并存或去重）。
- 无 runtime / YAML authoring 行为变更。
