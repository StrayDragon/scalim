# Tasks: c25-fix-test-sleep-governance-gate

## 1. Fix residual `time.sleep` polling in tests

- [ ] 1.1 Refactor `tests/workflow/test_workflow_resources_coverage.py`: replace `while` + `sleep(0.001)` polling with `threading.Event` coordination; writer `set()`, reader `event_wait(...)`.
- [ ] 1.2 Refactor `tests/ob/test_viz_hook.py`: replace sleep used for async IO / file visibility with `event_wait` or retry + `event_wait` per design evaluation.

## 2. Governance script and allowlist

- [ ] 2.1 Add `scripts/check-no-test-sleep.py` that scans `tests/**/*.py` for `time.sleep` and exits non-zero on unauthorized use.
- [ ] 2.2 Add an explicit allowlist excluding `tests/fixtures/workflow_loaders.py` (slow-loader simulation) and document how to add future allowed paths.
- [ ] 2.3 Integrate the check into `just qa` via the `quick-check-only-py` chain (or equivalent fail-fast stage).

## 3. Verification

- [ ] 3.1 Run `just qa` / `just test-gate`.
- [ ] 3.2 Run `just openspec-check`.
