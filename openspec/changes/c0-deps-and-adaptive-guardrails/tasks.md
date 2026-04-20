## 1. Dependency CVE remediation (uv.lock minimal delta)

- [ ] 1.1 Re-lock `uv.lock` with minimal perturbation: run `uv lock -P pytest -P marimo -P uv` and review the diff.
- [ ] 1.2 If resolver requires it, adjust `pyproject.toml` constraints for the affected dev groups/extras only (keep runtime Python 3.6 boundary intact).
- [ ] 1.3 Re-run the same audit workflow (`uv export` + `pip-audit -s osv --no-deps --disable-pip`) and attach the “before/after” finding summary to the PR description (no new docs required).

## 2. Guardrail for explicit max_workers (DoS hardening)

- [ ] 2.1 Add a hard cap + diagnostic warning for explicit `max_workers` in `resolve_adaptive_max_workers` (`src/scalim/execution/adaptive/_internal/loadref_scheduler_support.py`).
- [ ] 2.2 Add entrypoint validation/guardrails so external input cannot silently amplify concurrency (`src/scalim/dsl/yaml_dsl/workflow_entrypoints.py`, `src/scalim/execution/contracts.py`).
- [ ] 2.3 Add unit tests for the cap and warning behavior (cover: negative/zero/default, large explicit values, cpu_count edge cases).

## 3. Adaptive hang/timeout fail-fast diagnostics

- [ ] 3.1 Introduce an optional timeout setting (default off) that bounds waiting in `run_tasks_in_pool` (`src/scalim/execution/adaptive/submission_unit.py`), producing an actionable error on timeout (include pending task keys/count).
- [ ] 3.2 Ensure pipeline error/timeout paths do not indefinitely block on threadpool shutdown; document the limitation that Python threads cannot be force-killed (`src/scalim/execution/pipeline/base/pipeline.py`, `src/scalim/execution/pipeline/base/_adaptive_pool.py`).
- [ ] 3.3 Add a regression test that simulates a “stuck” task and asserts fail-fast diagnostics (use a controlled Event-based block; avoid flaky sleep-driven timing).

## 4. Fix head-of-line blocking in task submission loop

- [ ] 4.1 Refactor token acquisition order in `run_tasks_in_pool` to avoid cross-pool head-of-line blocking (`src/scalim/execution/adaptive/submission_unit.py`).
- [ ] 4.2 Add a regression test covering two pools where one pool is saturated but the other pool continues to make submission progress (no effective concurrency collapse to 1).

## 5. Documentation + thread-safety usage constraints

- [ ] 5.1 Update `docs/doc/architecture/parallel-modes.md` to explicitly describe replay ordering semantics (typed hooks vs observer/on_event) and streaming sink implications (hand-written SSOT; do not edit any injected blocks).
- [ ] 5.2 Document `preloaded_cache` concurrency constraints and recommendations (`PreloadCache` vs per-run cache) near the engine API (`src/scalim/execution/engine.py`) and/or the docs.
- [ ] 5.3 Clarify the supported model for hook registration lifecycle (HookCaptureManager snapshot assumption; discourage register/unregister during `run`) (`src/scalim/execution/adaptive/capture.py`, `src/scalim/execution/engine.py`).

## 6. Verification / gates

- [ ] 6.1 Run `just qa` and fix only regressions introduced by this change.
- [ ] 6.2 Run `just openspec-check` to ensure sanitize + validate pass for the new OpenSpec artifacts.

