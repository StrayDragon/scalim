## 1. Typed managed artifact wiring

- [ ] 1.1 Extend execution/runtime contracts so outputs consumed by `xlsx_memory` write nodes publish per-output typed managed artifacts as the SSOT, rather than only `in_memory_csv_outputs`.
- [ ] 1.2 Route workflow `write_sheet` / `append_sheet` nodes targeting `books.kind=xlsx_memory` to consume those typed managed artifacts, while keeping `csv` / `xlsx_file` consumers on their existing `CSV`-equivalent path.
- [ ] 1.3 Ensure typed managed artifacts are released with the existing workflow-managed lifecycle rules after the final `xlsx_memory` consumer or on workflow failure.

## 2. Sheetbook typed runtime

- [ ] 2.1 Refactor `sheetbook` plan/segment storage to keep canonical field keys plus typed `FieldValue` rows, assuming `c0-xlsx-memory-internal-field-headers` semantics are already in place.
- [ ] 2.2 Update `book_sheet_rows` / `iter_sheetbook_sheet_rows` to return canonical field keys with preserved `FieldValue` values by default, without introducing a `typed` compatibility flag.
- [ ] 2.3 Move spreadsheet-specific serialization/escaping to the final `export_xlsx` commit boundary so internal `xlsx_memory` paths no longer stringify values early.

## 3. Regression coverage and validation

- [ ] 3.1 Add focused tests covering `int` / `Decimal` / `bool` preservation, `str(\"007\")` staying a string, and `Decimal` not being implicitly downgraded to `float` on the `xlsx_memory` path.
- [ ] 3.2 Add coverage for the explicit non-goal boundary that legacy empty-string text is not heuristically promoted to `None` without dedicated null semantics.
- [ ] 3.3 Keep SSOT in `openspec/changes/c0-xlsx-memory-type-preservation/*` and `openspec/specs/*`; if docs/spec indexes or injected blocks need refresh, use `just gen-docs`, then validate with `just openspec-check` and the smallest relevant pytest subset.
