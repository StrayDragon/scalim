# workflow-shared-output-containers (delta) Specification

## MODIFIED Requirements

### Requirement: WorkflowArtifactsDirectory MUST fail-fast on any non-controller thread write path

`WorkflowArtifactsDirectory` is workflow-managed shared mutable state. All mutating APIs MUST be treated as controller-only writers, including:

- `publish` / `discard`
- in-memory artifact cleanup helpers (e.g. `discard_in_memory_*`, `discard_all_in_memory_*`, `discard_all_in_memory_rows`)

Any worker thread (non-controller thread) calling these writer APIs MUST be considered an implementation error and MUST fail-fast.

#### Scenario: worker misuse of in-memory discard helpers fails fast
- **GIVEN** workflow is running with concurrency enabled (`max_concurrency > 1`)
- **WHEN** a worker thread calls an in-memory discard/cleanup helper on `WorkflowArtifactsDirectory`
- **THEN** the call MUST fail-fast (e.g. raise `RuntimeError`) instead of silently mutating shared state

### Requirement: The single-writer contract MUST be consistently enforced across all artifacts cleanup paths

The single-writer contract MUST NOT be partially enforced only on “main” APIs while leaving helper methods unguarded. Helper methods that mutate internal dicts MUST carry the same enforcement as `publish/discard`.

#### Scenario: refactor does not introduce unguarded helper writes
- **WHEN** new artifact helper APIs are added or existing helpers are refactored
- **THEN** any helper that mutates workflow-managed artifacts MUST include the same owner-thread enforcement
