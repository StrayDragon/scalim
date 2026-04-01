## 1. Typed managed artifact wiring

- [x] 1.1 Refactor execution/runtime contracts so workflow-managed artifact semantics are explicit runtime contracts (for example, separate `in_memory_csv_outputs` and `in_memory_rows_outputs`) rather than being encoded via `OutputSpec(format=csv)`.
- [x] 1.2 Introduce a managed-artifact sink/plan abstraction in output composition so `xlsx_memory`-bound outputs publish per-output typed managed artifacts as SSOT, while `CSV`-equivalent consumers may still receive derived string artifacts.
- [x] 1.3 Ensure per-output typed managed artifacts participate in the existing workflow-managed lifecycle rules, including reference-counted release after the final `xlsx_memory` consumer and discard on workflow failure.

## 2. Sheetbook typed runtime

- [x] 2.1 Introduce a unified tabular artifact adapter for internal write/read paths so `sheetbook` no longer depends on `input_csv`-shaped APIs as its internal model.
- [x] 2.2 Refactor `sheetbook` plan/segment storage and `book_sheet_rows` / `iter_sheetbook_sheet_rows` to use canonical field keys plus preserved typed `FieldValue` rows by default, without introducing a `typed` compatibility flag.
- [x] 2.3 Move spreadsheet-specific serialization/escaping to the final `export_xlsx` commit boundary so internal `xlsx_memory` paths no longer stringify values early.

## 3. Regression coverage and validation

- [x] 3.1 Add focused tests covering `int` / `Decimal` / `bool` preservation, `str(\"007\")` staying a string, and `Decimal` not being implicitly downgraded to `float` on the `xlsx_memory` path.
- [x] 3.2 Add coverage for the explicit non-goal boundary that legacy empty-string text is not heuristically promoted to `None` without dedicated null semantics.
- [x] 3.3 Keep SSOT in `openspec/changes/c0-xlsx-memory-type-preservation/*` and `openspec/specs/*`; if docs/spec indexes or injected blocks need refresh, use `just gen-docs`, then validate with `just openspec-check` and the smallest relevant pytest subset.
