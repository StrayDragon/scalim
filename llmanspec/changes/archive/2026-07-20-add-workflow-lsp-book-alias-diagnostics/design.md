# Design: add-workflow-lsp-book-alias-diagnostics

## Decision

在 `_collect_workflow_diagnostics` 中，于 schema + unknown-fields 之后（或之前），对 `workflow.resources.books` 复用 demand 侧 books 静态校验（`ConfigValidator._validate_resource_output_paths` 的 books 子集 / 同等消息函数），并把路径前缀改为 `workflow.resources.books.*`。

## Non-goals

- 不做 workflow compile / demand 递归校验 / runtime run。
- 不改 JSON Schema 结构（authoring 仍仅 `xlsx`）。
- 不强制本变更去重 demand 侧 duplicate Unknown field（可顺带对 workflow 同 path 去重 unknown，若实现成本低）。

## Dedup

若同一 canonical path 已有 books 迁移语义错误，workflow unknown-field 对该 path MUST NOT 再追加重复 `Unknown field`（降低噪声）。
