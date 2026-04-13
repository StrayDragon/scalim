# preload-cache-thread-safety (delta) Specification

## ADDED Requirements

### Requirement: PreloadCache waiter path MUST read inflight and fallback state under the per-source lock

After an in-flight waiter’s `Event` becomes done, the implementation MUST NOT read `inflight.error`, `inflight.value`, or decide fallback from `_data` outside the per-source lock. All such reads MUST occur in the same critical section pattern as existing `_data` access so that free-threaded runtimes cannot observe torn or inconsistent inflight fields.

#### Scenario: Waiter observes completed load under lock
- **WHEN** a thread waits on `inflight.done` in `get_or_load` and the wait returns
- **THEN** the implementation MUST acquire the per-source lock before reading `inflight.error` / `inflight.value` or returning a value from `_data` for that source
- **AND** the returned value or raised exception MUST match the same ordering guarantees as the non-waiter code paths

### Requirement: PreloadCache mapping introspection MUST be safe under concurrent mutation

`__iter__`, `__len__`, and `__contains__` on `PreloadCache` MUST operate on `_data` only while holding the existing global lock used for lock-table coordination (`_global_lock`). Iteration MUST use a snapshot of keys (or equivalent) so that concurrent `get_or_load` / writes do not cause dict-mutation errors or skipped elements during iteration.

#### Scenario: Concurrent iteration and load
- **WHEN** one thread iterates or calls `len` / `__contains__` while other threads call `get_or_load` or mutate the cache
- **THEN** those introspection operations MUST NOT raise exceptions due to concurrent dict modification
- **AND** `__iter__` MUST yield a consistent snapshot of keys as of the time the snapshot was taken

### Requirement: PreloadCache MUST document its thread-safety contract

The class-level documentation MUST state which operations are synchronized, which lock protects `_data` vs lock-table vs inflight coordination, and that the implementation targets correctness under free-threaded Python as well as GIL-backed CPython.

#### Scenario: Maintainers understand boundaries
- **WHEN** a developer reads the `PreloadCache` docstring
- **THEN** they MUST be able to see explicit thread-safety boundaries and assumptions without reading implementation details alone

### Requirement: PreloadCache concurrency MUST be covered by tests

The test suite MUST include multi-threaded coverage that exercises concurrent `get_or_load` together with concurrent iteration (`__iter__` / `len` / membership) on the same instance, in addition to existing behavior tests.

#### Scenario: Regression guard for thread-safety fixes
- **WHEN** CI runs the workflow/cache-related test gate
- **THEN** tests MUST exercise concurrent waiters and concurrent introspection without flaky failures
