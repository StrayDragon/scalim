# Tasks: c30-harden-cache-pool-eviction-safety

## 1. Harden `WorkflowCachePool` eviction and close

- [ ] 1.1 Keep `_evict_entry` behavior of skipping `entry.loading` entries; ensure no path removes a loading entry from `_entries` without coordinating with `entry.lock` / load completion.
- [ ] 1.2 Implement `close()`: phase 1 — under `self._lock`, collect entries with `loading=True`; release global lock; for each such entry, acquire `entry.lock` to wait for `load_fn` completion; phase 2 — under `self._lock`, evict remaining keys via `_evict_entry` (or equivalent) when no entries are loading.
- [ ] 1.3 (Optional) Add `_closing` set at `close()` entry under global lock; make `get_or_load` fail fast when `_closing` is true, with tests and documented error semantics.

## 2. Concurrent tests

- [ ] 2.1 Add test: slow `load_fn` (controlled by `threading.Event`); call `close()` while load is in progress; assert close waits and no duplicate load / orphan write.
- [ ] 2.2 Add test: eviction concurrent with `get_or_load` on same key; assert no duplicate load and consistent cache state.

## 3. Verification

- [ ] 3.1 Run `just qa` / `just test-gate`.
- [ ] 3.2 Run `just openspec-check`.
