# Tasks: c20-fix-test-timeout-ssot-unify

## 1. Replace hardcoded timeouts

- [ ] 1.1 Update `tests/workflow/test_workflow_cache_pool.py`: replace `_TIMEOUT_S` and `wait(timeout=0.1)` with `event_wait` + `CI_TIMEOUT_S` (or other SSOT helpers from `tests/support/testing_utils.py`).
- [ ] 1.2 Update `tests/ob/test_viz_hook.py`: replace hardcoded timeouts / `time.sleep`+timeout patterns with `event_wait` / `CI_TIMEOUT_S` as appropriate.
- [ ] 1.3 Update `tests/workflow/test_workflow_entrypoints_smoke.py`: replace bare `30.0` with `CI_TIMEOUT_S` or `CI_TIMEOUT_S * 3` (with a comment for long-flow smoke) per design.
- [ ] 1.4 Audit remaining `tests/` for inconsistent timeout literals and align with SSOT helpers.

## 2. Optional governance

- [ ] 2.1 (Optional) Add a governance scan for `timeout=` literals under `tests/` to enforce SSOT usage.

## 3. Verification

- [ ] 3.1 Run `just qa` / `just test-gate`.
- [ ] 3.2 Run `just openspec-check`.
