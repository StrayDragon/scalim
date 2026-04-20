# single-writer-model-safety Specification

## Purpose
Establish and enforce a single-writer threading model for workflow execution state, ensuring that write operations to shared runtime structures are either owned by a controller thread or protected by locks in free-threaded Python runtimes, with debug assertions to catch violations early.

## Related Concepts
- WorkflowCtxStore (workflow execution state storage)
- WorkflowArtifactsDirectory (artifacts and outputs container)
- Single-writer threading model (controller-thread ownership)
- Free-threaded Python (no-GIL runtime)
- Debug assertions (development-time contract validation)
- Write-node scheduling (demand future management)

## Requirements
### Requirement: WorkflowCtxStore and WorkflowArtifactsDirectory write operations MUST assert controller-thread ownership in debug builds

All mutating entry points on `WorkflowCtxStore` and `WorkflowArtifactsDirectory` (e.g. publish and equivalent writes) MUST assert that `threading.current_thread().ident` equals the thread id recorded at construction (`_owner_thread_id`). Assertions MUST be disabled under Python `-O` so normal production runs incur no overhead.

#### Scenario: Wrong thread calls write method in debug mode
- **WHEN** a write method runs on a thread other than the owner thread and assertions are enabled
- **THEN** the implementation MUST fail fast with a clear assertion message identifying the single-writer contract violation

#### Scenario: Wrong thread mutates artifacts directory in debug mode
- **WHEN** a write runs off the owner thread with assertions enabled
- **THEN** the implementation MUST assert with an explicit single-writer violation message

### Requirement: Write-node scheduling MUST assert no in-flight demand futures

When the controller schedules a write node, the implementation MUST assert that no demand futures are in-flight, preserving the invariant that writes run only when no concurrent demand work is submitted.

#### Scenario: Write scheduled while submitted futures exist
- **WHEN** a write node is about to be scheduled while demand futures are in-flight
- **THEN** assertions enabled MUST catch the violation; with assertions disabled, behavior follows existing code paths (no new semantic requirement beyond current model)

### Requirement: Free-threaded Python MUST enable lock-guarded access to shared workflow stores

When the interpreter reports a free-threaded (no-GIL) runtime, `WorkflowCtxStore` and `WorkflowArtifactsDirectory` MUST protect their read/write methods with appropriate locking so dict-backed state remains correct without relying on GIL happens-before. On GIL-backed builds, locking MUST be a no-op path with no extra overhead.

#### Scenario: Runtime is free-threaded
- **WHEN** the runtime is free-threaded
- **THEN** reads and writes on these structures MUST occur under lock discipline so concurrent access cannot corrupt internal state

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

