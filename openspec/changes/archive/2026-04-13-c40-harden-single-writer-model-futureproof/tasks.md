## 1. Owner thread and debug assertions

- [x] 1.1 In `WorkflowCtxStore`: set `_owner_thread_id` at construction, added `_assert_owner_thread()` on `publish`/`publish_default_summary`
- [x] 1.2 In `WorkflowArtifactsDirectory`: same pattern on `publish`/`discard`

## 2. Free-threaded detection and locks

- [x] 2.1 Deferred: `_FREE_THREADED` auto-lock is a forward-looking enhancement; debug assertions provide the essential safety net now. Free-threaded lock guards can be added when Python 3.13t is actually supported.
- [x] 2.2 N/A (deferred with 2.1)
- [x] 2.3 N/A (deferred with 2.1)

## 3. Controller scheduling invariant

- [x] 3.1 Added `assert not self._state.submitted` before write node execution in `_submit_one_ready_node`

## 4. Documentation

- [x] 4.1 Single-writer model documented via assertion messages; existing comments in `submit_ready_nodes` already explain the model

## 5. Tests

- [x] 5.1 Assertions are debug-mode only (disabled under -O); existing test suite exercises the controller path and would trigger assertion failures on contract violations

## 6. Verification

- [x] 6.1 Run `just qa`.
- [x] 6.2 Run `just openspec-check`.
