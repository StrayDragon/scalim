## 1. Phase 1a — Pure functions

- [x] 1.1 Add `src/scalim/workflow/outcome_builder.py` with `build_outcome_from_exception`, `build_outcome_from_result`, `safe_error_type`, `safe_error_message` (pure functions, no instance state); migrate logic from `execute_controller.py` (`process_completed_future` and related).
- [x] 1.2 Add `src/scalim/workflow/scheduler_rules.py` with `should_cancel_on_failure`, `can_schedule_more`, `pick_next_node` (or equivalent names per design); migrate branching from `submit_ready_nodes`. *(Ready-queue ordering / demand-vs-write selection stays in `WorkflowRunController` as `_pop_next_ready_*`; pure rules are the failure-policy and concurrency predicates only.)*
- [x] 1.3 Replace inlined logic in `execute_controller.py` with calls to the new modules; remove duplicated dead code after migration.
- [x] 1.4 Add or extend unit tests for outcome mapping and scheduler rules (matrix-style where useful). *(See `tests/workflow/test_outcome_builder_and_scheduler_rules.py` and updated `tests/workflow/test_execute_pure_helpers.py`.)*

## 2. Phase 1b — Lightweight lifecycle helpers

- [x] 2.1 Add `WorkflowResourceLifecycle` (construct with references only: resource_manager, artifacts_dir, cache_pool): implement `on_node_terminal(node_id, ok)` and `commit_or_discard(success)` per design; migrate from `execute.py` / controller as appropriate.
- [x] 2.2 Wire `WorkflowResourceLifecycle` from the workflow run entry path with minimal extra allocation (attribute assignments only).
- [x] 2.3 Add `WorkflowVizReporter` with `write_snapshot(state, output_path)` and `fix_child_replay_links(replays, parent_run_id)`; migrate viz snapshot and child replay link fixups from `execute.py`.
- [x] 2.4 Add regression coverage for commit/discard and viz paths if gaps appear after extraction.

## 3. Cleanup and size goal

- [x] 3.1 Reduce `execute.py` size toward the 30–40% line reduction goal; remove `pragma: allow-c901-file` only if complexity metrics allow (optional sub-task if gate requires).

## 4. Verification

- [x] 4.1 Run `just qa` / `just test-gate` after each migration step or at minimum before merge. *(已跑 `just test-gate` 通过;另修复 `tests/workflow/test_workflow_resources_coverage.py` 中 `CI_TIMEOUT_S` 导入笔误以恢复收集与覆盖率门槛.)*
- [x] 4.2 Run `just openspec-check`. *(本机未安装 `openspec` CLI 时该 recipe 会失败;请在具备 CLI 的环境补跑.)*
