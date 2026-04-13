# workflow-execute-organization (delta) Specification

## MODIFIED Requirements

### Requirement: Workflow execution observable behavior MUST remain unchanged after Phase 1 refactor

Phase 1 MUST reorganize `execute.py` / `execute_controller.py` implementation into focused modules (`outcome_builder`, `scheduler_rules`, `WorkflowResourceLifecycle`, `WorkflowVizReporter`) without changing external semantics: outcomes, scheduling decisions, resource commit/discard, viz snapshots, and replay link behavior MUST remain byte-for-byte or logically equivalent to pre-change behavior for the same inputs and options.

#### Scenario: Regression parity after extraction
- **WHEN** the same workflow run configuration is executed before and after Phase 1 module extraction
- **THEN** observable results (outcomes, node states, events, artifacts lifecycle, viz outputs) MUST match prior behavior within the project’s existing equivalence tests or snapshot contracts

### Requirement: Phase 1 MUST avoid new hot-path allocation or abstraction overhead

Extraction MUST use module-level pure functions and small holder classes that only keep references (no deep copies). The implementation MUST NOT introduce abstract base classes, strategy/plugin indirection, or extra serialization. Per-run extra memory from new objects MUST remain negligible (on the order of a few references per run as stated in design).

#### Scenario: Performance characteristics preserved
- **WHEN** a representative workflow run executes on GIL-backed CPython
- **THEN** the refactor MUST NOT add material CPU or memory regressions attributable to new object churn or indirect dispatch on the primary execute path

### Requirement: Extracted modules MUST remain Python 3.6 compatible

New modules under `src/scalim/workflow/` MUST use the same Python 3.6 compatibility constraints as the rest of `scalim` (typing, dataclasses shims, no 3.7-only stdlib helpers unless shimmed).

#### Scenario: CI runs on minimum supported Python
- **WHEN** tests run on the repository’s Python 3.6 job or equivalent gate
- **THEN** the new modules MUST import and execute without syntax or stdlib availability errors

#### Scenario: Organization improves testability
- **WHEN** reviewers add or extend unit tests for `outcome_builder` and `scheduler_rules`
- **THEN** pure functions MUST be callable without constructing a full workflow runtime except where integration tests require it
