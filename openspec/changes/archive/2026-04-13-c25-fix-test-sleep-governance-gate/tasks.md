# Tasks: c25-fix-test-sleep-governance-gate

## 1. Fix residual `time.sleep` polling in tests

- [x] 1.1 Refactor `tests/workflow/test_workflow_resources_coverage.py`: replaced `time.sleep(0.001)` polling with `stop_reader.wait(timeout=0.001)` (Event-based)
- [x] 1.2 Refactor `tests/ob/test_viz_hook.py`: replaced `time.sleep(0.001)` with `stop.wait(timeout=0.001)` (Event-based)

## 2. Governance script and allowlist

- [x] 2.1 Added `scripts/check-no-test-sleep.py` with AST-based scanning
- [x] 2.2 Allowlist includes `tests/fixtures/workflow_loaders.py` with instructions for adding new paths
- [x] 2.3 Integrated `check-no-test-sleep` into `quick-check-only-py` chain in justfile

## 3. Verification

- [x] 3.1 Run `just qa` / `just test-gate`.
- [x] 3.2 Run `just openspec-check`.
