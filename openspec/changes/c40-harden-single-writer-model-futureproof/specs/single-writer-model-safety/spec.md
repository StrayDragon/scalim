# single-writer-model-safety (delta) Specification

## ADDED Requirements

### Requirement: WorkflowCtxStore write operations MUST assert controller-thread ownership in debug builds

All mutating entry points on `WorkflowCtxStore` (e.g. publish and equivalent writes) MUST assert that `threading.current_thread().ident` equals the thread id recorded at construction (`_owner_thread_id`). Assertions MUST be disabled under Python `-O` so normal production runs incur no overhead.

#### Scenario: Wrong thread calls publish in debug mode
- **WHEN** a write method runs on a thread other than the owner thread and assertions are enabled
- **THEN** the implementation MUST fail fast with a clear assertion message identifying the single-writer contract violation

### Requirement: WorkflowArtifactsDirectory write operations MUST assert controller-thread ownership in debug builds

The same single-writer assertion pattern as `WorkflowCtxStore` MUST apply to mutating methods on `WorkflowArtifactsDirectory`, with zero cost when assertions are stripped.

#### Scenario: Wrong thread mutates artifacts directory in debug mode
- **WHEN** a write runs off the owner thread with assertions enabled
- **THEN** the implementation MUST assert with an explicit single-writer violation message

### Requirement: Write-node scheduling MUST assert no in-flight demand futures

When the controller schedules a write node, the implementation MUST assert that `len(self._state.submitted) == 0` (no in-flight demand futures), preserving the invariant that writes run only when no concurrent demand work is submitted.

#### Scenario: Write scheduled while submitted futures exist
- **WHEN** a write node is about to be scheduled and `submitted` is non-empty
- **THEN** assertions enabled MUST catch the violation; with assertions disabled, behavior follows existing code paths (no new semantic requirement beyond current model)

### Requirement: Free-threaded Python MUST enable lock-guarded access to shared workflow stores

When the interpreter reports a free-threaded (no-GIL) runtime via `sys.flags` (e.g. `nogil` / `no_gil` as available on the running version), `WorkflowCtxStore` and `WorkflowArtifactsDirectory` MUST protect their read/write methods with `threading.Lock` (or equivalent) so dict-backed state remains correct without relying on GIL happens-before. On Python 3.6 and GIL-backed builds where the flag is absent, the lock MUST be a no-op path with no extra locking overhead.

#### Scenario: Runtime is free-threaded
- **WHEN** `_FREE_THREADED` is true for the process
- **THEN** reads and writes on these structures MUST occur under the same lock discipline so concurrent access cannot corrupt internal dicts

### Requirement: Single-writer model MUST be documented

Documentation (module or class-level) MUST describe the single-writer assumption, the role of debug assertions, and free-threaded locking, so future scheduler changes do not silently break the contract.

#### Scenario: Contributor reads workflow execute artifacts docs
- **WHEN** a maintainer looks up thread-safety for ctx store and artifacts directory
- **THEN** they MUST find an explicit description of single-writer semantics and free-threaded safeguards

### Requirement: Assertions and free-threaded locking MUST be covered by tests

Tests MUST validate that debug assertions fire on intentional contract violations where practical, and that the free-threaded detection path selects the locking branch without breaking GIL-backed CI (e.g. via controlled flags or unit-level seams as appropriate).

#### Scenario: CI exercises new safety paths
- **WHEN** the test gate runs
- **THEN** new or updated tests MUST cover assertion behavior and/or lock selection logic without introducing flaky timing-dependent failures
