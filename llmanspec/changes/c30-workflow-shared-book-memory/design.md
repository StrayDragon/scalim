# Design: workflow-shared-book-memory

## Dependency

MUST 在 `book-write-policy-python-ssot` 提供的 Python `BookBudgetPolicy` / resources policy 挂载点可用后实现 P1。  
P0（释放）可与上游并行开发，但归档顺序建议：先归档上游，再归档本 change。

## Current model (keep)

```text
demand run → managed ROWS artifact
    → write node (controller single-writer) materialize → plan segments
    → (optional) book_sheet_rows reads plan
    → success: openpyxl write_only commit → staging → publish
    → failure: discard (no partial final xlsx)
```

## P0 release strategy

1. After a write node successfully applies segments for a managed artifact that has **no further consumers**, discard the demand-side in-memory rows/csv handle.
2. Visibility rules for `book_sheet_rows` remain plan-based (unchanged).
3. On `commit_all` / `discard_all`, clear segment row lists (or drop plans) to release peak ASAP.

Evidence: prefer a small before/after memory or object-count probe under `.tmp/`（不提交）或 pytest 用可控行数断言「双驻留窗口缩短」（若难测内存，则测 discard API 调用次数 / 弱引用）。

## P1 budget

- Read limits only from effective Python policy
- `xlsx_memory` MUST enforce; document whether `xlsx_file` gets the same cell budget（建议：同策略可选启用，默认 unlimited 以保兼容）

## Out of scope details

- Demand-level `StreamingColumnExcelSink`：另案；若转正 MUST 把 flush 放进 Python/profile，禁止 YAML
- Profiles (`memory`/`balanced`/`speed`)：可在后续 change 挂接；本 design 只预留「释放积极程度」由 policy/profile 表达的可能性

## Source links

- futures R2: `llmanspec/futures/xlsx-file-numeric-type-loss/future.md`
- notplan (reframe later): `llmanspec/notplan/c1-streaming-xlsx-output/`
- notplan carrier: `llmanspec/notplan/c1-runtime-performance-profiles/`
