# language: zh-CN
# capability: execution-safety-single-writer
# purpose: Establish and enforce a single-writer threading model for workflow execution state, ensuring that write operations to shared runtime structures are either owned by a controller thread or protected by [rev:c25]
# scope: src/scalim/
功能: execution-safety-single-writer

  @req:r44 @human
  场景: WorkflowCtxStore and WorkflowArtifactsDirectory write operations MUST assert construction
    - All mutating entry points on `WorkflowCtxStore` and `WorkflowArtifactsDirectory` (e.g. publish and equivalent writes) MUST assert that `threading.current_thread().ident` equals the thread id recorded at construction (`_owner_thread_id`). Assertions MUST be disabled under Python `-O` so normal production runs incur no overhead.
    当 a write method runs on a thread other than the owner thread and assertions are enabled
    那么 the implementation MUST fail fast with a clear assertion message identifying the single-writer contract violation
    当 a write runs off the owner thread with assertions enabled
    那么 the implementation MUST assert with an explicit single-writer violation message
  @req:r288 @human
  场景: Write-node scheduling MUST assert no in-flight demand futures
    - When the controller schedules a write node, the implementation MUST assert that no demand futures are in-flight, preserving the invariant that writes run only when no concurrent demand work is submitted.
    当 a write node is about to be scheduled while demand futures are in-flight
    那么 assertions enabled MUST catch the violation; with assertions disabled, behavior follows existing code paths (no new semantic requirement beyond current model)
  @req:r412 @human
  场景: Free-threaded Python MUST enable lock-guarded access to shared workflow stores
    - When the interpreter reports a free-threaded (no-GIL) runtime, `WorkflowCtxStore` and `WorkflowArtifactsDirectory` MUST protect their read/write methods with appropriate locking so dict-backed state remains correct without relying on GIL happens-before. On GIL-backed builds, locking MUST be a no-op path with no extra overhead.
    当 the runtime is free-threaded
    那么 reads and writes on these structures MUST occur under lock discipline so concurrent access cannot corrupt internal state
  @req:r507 @human
  场景: Single-writer model MUST be documented
    - Documentation (module or class-level) MUST describe the single-writer assumption, the role of debug assertions, and free-threaded locking, so future scheduler changes do not silently break the contract.
    当 a maintainer looks up thread-safety for ctx store and artifacts directory
    那么 they MUST find an explicit description of single-writer semantics and free-threaded safeguards
  @req:r584 @human
  场景: Assertions and free-threaded locking MUST be covered by tests
    - Tests MUST validate that debug assertions fire on intentional contract violations where practical, and that the free-threaded detection path selects the locking branch without breaking GIL-backed CI (e.g. via controlled flags or unit-level seams as appropriate).
    当 the test gate runs
    那么 new or updated tests MUST cover assertion behavior and/or lock selection logic without introducing flaky timing-dependent failures
