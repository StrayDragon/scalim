## 1. Canonical key enforcement

- [x] 1.1 Refactor `xlsx_memory` write/read paths so workflow-managed artifacts and sheetbook internal rows use only canonical field keys.
- [x] 1.2 Update `book_sheet_rows` / `iter_sheetbook_sheet_rows` to always return canonical field keys and never leak display headers.
- [x] 1.3 Add compile-time or runtime validation that rejects `xlsx_memory + align_by=header` with an actionable migration error.

## 2. Result-side export metadata

- [x] 2.1 Add sheet-level export header metadata to the `sheetbook` plan structure, keeping it separate from internal row keys.
- [x] 2.2 Render `export_xlsx` headers from that result-side metadata without changing `xlsx_file` behavior.
- [x] 2.3 Enforce a deterministic single export-header baseline per `xlsx_memory` sheet and fail fast on silent replacement attempts.

## 3. Regression coverage and spec validation

- [x] 3.1 Add focused tests covering: `header_fields_output_by=name` with `book_sheet_rows`, rejection of `xlsx_memory + align_by=header`, and `export_xlsx` display-header rendering.
- [x] 3.2 Keep SSOT in `openspec/changes/c0-xlsx-memory-internal-field-headers/*` and `openspec/specs/*`; if docs/spec indexes or injected blocks need refresh, use `just gen-docs` rather than editing generated output directly.
- [x] 3.3 Validate acceptance with `just openspec-check` plus the smallest relevant pytest subset before widening to broader QA.
