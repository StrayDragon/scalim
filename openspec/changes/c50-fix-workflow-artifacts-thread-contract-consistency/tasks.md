## 1. Enforce Single-Writer Contract

- [ ] 1.1 Add `_assert_owner_thread()` enforcement to all `WorkflowArtifactsDirectory` mutating helpers (`discard_in_memory_*`, `discard_all_in_memory_*`, `discard_all_in_memory_rows`) in `src/scalim/workflow/artifacts.py`.
- [ ] 1.2 Ensure the raised error type/message remains consistent with existing owner-thread guards (fail-fast as implementation error).

## 2. Tests

- [ ] 2.1 Add unit tests that force owner-thread mismatch (e.g. set `_owner_thread_id = -1`) and assert the new helper methods fail-fast with `RuntimeError`.
- [ ] 2.2 Keep tests focused on contract enforcement (avoid depending on workflow scheduler/controller internals).

## 3. QA / Governance

- [ ] 3.1 Run `uv run pytest tests/workflow/ -q` and ensure coverage gate remains stable.
- [ ] 3.2 Run `uv run python scripts/check-no-cover.py --check` (no new ungoverned pragmas).
- [ ] 3.3 Run `just openspec-check` to ensure OpenSpec artifacts stay valid.

## 4. SSOT / Generated Artifacts

- [ ] 4.1 Confirm this change does not touch any generated files (`*.gen.*`) or injected blocks; SSOT is the hand-written runtime code and tests, verified by `just qa`.
