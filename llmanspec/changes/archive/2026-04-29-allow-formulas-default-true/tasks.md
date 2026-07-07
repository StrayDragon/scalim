## 1. Runtime Defaults

- [x] 1.1 Update CSV sinks default `allow_formulas=True` and keep `allow_formulas=False` as escape mode
- [x] 1.2 Update Excel sinks default `allow_formulas=True` and keep `allow_formulas=False` as escape mode
- [x] 1.3 Update workflow books/resources parsing so missing `allow_formulas` defaults to `true` (xlsx_file + xlsx_memory.export_xlsx)

## 2. Tests

- [x] 2.1 Update sink tests to reflect new default (no leading `'` unless `allow_formulas=False`)
- [x] 2.2 Update workflow resource/export tests to reflect new default and keep explicit escape coverage

## 3. Verification

- [x] 3.1 Run `just openspec-check` to ensure artifacts validate (no generated files edited)
- [x] 3.2 Run `just qa` (or at least the relevant pytest subsets) to ensure behavior and regressions are covered
