# language: zh-CN
# capability: workflow-execute-organization
# purpose: 重构 workflow execute 模块结构（extract outcome_builder/scheduler_rules/resource_lifecycle/viz_reporter），不改变外部可观测行为、不增加热路径开销，并保持 Python 3.6 兼容。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: workflow-execute-organization

  @req:r87 @human
  场景: Workflow execution observable behavior MUST remain unchanged after Phase 1 refac
    - Phase 1 MUST reorganize `execute.py` / `execute_controller.py` implementation into focused modules (`outcome_builder`, `scheduler_rules`, `WorkflowResourceLifecycle`, `WorkflowVizReporter`) without changing external semantics: outcomes, scheduling decisions, resource commit/discard, viz snapshots, and replay link behavior MUST remain byte-for-byte or logically equivalent to pre-change behavior for the same inputs and options.

  @req:r330 @human
  场景: Phase 1 MUST avoid new hot-path allocation or abstraction overhead
    - Extraction MUST use module-level pure functions and small holder classes that only keep references (no deep copies). The implementation MUST NOT introduce abstract base classes, strategy/plugin indirection, or extra serialization. Per-run extra memory from new objects MUST remain negligible (on the order of a few references per run as stated in design).

  @req:r452 @human
  场景: Extracted modules MUST remain Python 3.6 compatible
    - New modules under `src/scalim/workflow/` MUST use the same Python 3.6 compatibility constraints as the rest of `scalim` (typing, dataclasses shims, no 3.7-only stdlib helpers unless shimmed).
  @req:r87 @human
  场景: regression-parity-after-extraction
    - 必须成立：当 the same workflow run configuration is executed before and after Phase 1 module extraction；那么 observable results (outcomes, node states, events, artifacts lifecycle, viz outputs) MUST match prior behavior within the project’s existing equivalence tests or snapshot contracts
    当 the same workflow run configuration is executed before and after Phase 1 module extraction
    那么 observable results (outcomes, node states, events, artifacts lifecycle, viz outputs) MUST match prior behavior within the project’s existing equivalence tests or snapshot contracts
  @req:r330 @human
  场景: performance-characteristics-preserved
    - 必须成立：当 a representative workflow run executes on GIL-backed CPython；那么 the refactor MUST NOT add material CPU or memory regressions attributable to new object churn or indirect dispatch on the primary execute path
    当 a representative workflow run executes on GIL-backed CPython
    那么 the refactor MUST NOT add material CPU or memory regressions attributable to new object churn or indirect dispatch on the primary execute path
  @req:r452 @human
  场景: ci-runs-on-minimum-supported-python
    - 必须成立：当 tests run on the repository’s Python 3.6 job or equivalent gate；那么 the new modules MUST import and execute without syntax or stdlib availability errors
    当 tests run on the repository’s Python 3.6 job or equivalent gate
    那么 the new modules MUST import and execute without syntax or stdlib availability errors

  @req:r452 @human
  场景: organization-improves-testability
    - 必须成立：当 reviewers add or extend unit tests for `outcome_builder` and `scheduler_rules`；那么 pure functions MUST be callable without constructing a full workflow runtime except where integration tests require it
    当 reviewers add or extend unit tests for `outcome_builder` and `scheduler_rules`
    那么 pure functions MUST be callable without constructing a full workflow runtime except where integration tests require it
