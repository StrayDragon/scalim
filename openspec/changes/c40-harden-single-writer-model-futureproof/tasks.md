## 1. Owner thread and debug assertions

- [ ] 1.1 In `src/scalim/workflow/execute.py` (`WorkflowCtxStore`), set `_owner_thread_id` at construction and add `assert threading.current_thread().ident == self._owner_thread_id` (with clear message) on all write entry points.
- [ ] 1.2 In `src/scalim/workflow/artifacts.py` (`WorkflowArtifactsDirectory`), apply the same owner-thread assertion pattern on write methods.

## 2. Free-threaded detection and locks

- [ ] 2.1 Add `_FREE_THREADED` detection using `sys.flags` (`nogil` / `no_gil` / `hasattr` pattern) compatible with Python 3.6.
- [ ] 2.2 When `_FREE_THREADED` is true, guard `WorkflowCtxStore` read/write methods with `threading.Lock`; when false, use a Python 3.6–compatible no-op context manager (no `contextlib.nullcontext`).
- [ ] 2.3 Apply the same lock vs no-op pattern to `WorkflowArtifactsDirectory`.

## 3. Controller scheduling invariant

- [ ] 3.1 In `src/scalim/workflow/execute_controller.py`, when submitting a write node, assert `len(self._state.submitted) == 0` with a message that write must not run while demand futures are in-flight.

## 4. Documentation

- [ ] 4.1 Document the single-writer model, assertion intent, and free-threaded locking in the relevant workflow module or class docstrings.

## 5. Tests

- [ ] 5.1 Add tests that validate assertion behavior on contract violations and/or locking branch selection as feasible without flakiness.

## 6. Verification

- [ ] 6.1 Run `just qa`.
- [ ] 6.2 Run `just openspec-check`.
