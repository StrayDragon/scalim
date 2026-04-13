# Tasks: c20-fix-test-timeout-ssot-unify

## 1. Replace hardcoded timeouts

- [x] 1.1 Update `tests/workflow/test_workflow_cache_pool.py`: replaced `_TIMEOUT_S` and `wait(timeout=0.1)` with `CI_TIMEOUT_S`/`NEGATIVE_TIMEOUT_S`/`event_wait`/`join_or_fail`
- [x] 1.2 Update `tests/ob/test_viz_hook.py`: replaced `t.join(timeout=5.0)` with `CI_TIMEOUT_S`
- [x] 1.3 Update `tests/workflow/test_workflow_entrypoints_smoke.py`: replaced `30.0` with `CI_TIMEOUT_S * 3` and `10.0` with `CI_TIMEOUT_S`
- [x] 1.4 Audited remaining `tests/` for inconsistent timeout literals — all aligned

## 2. Optional governance

- [x] 2.1 No remaining timeout literals; governance scan not needed at this time

## 3. Verification

- [x] 3.1 Run `just qa` / `just test-gate`.
- [x] 3.2 Run `just openspec-check`.
