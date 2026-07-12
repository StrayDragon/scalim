## 1. Replace wall-clock timestamp order assertions

- [x] 1.1 将 `test_workflow_pipeline_allows_cross_stage_overlap_under_concurrency` 的因果顺序断言改为 `Event.seq`；overlap 由 Event-gate releasing loader 证明
- [x] 1.2 将 `test_workflow_stage_barrier_blocks_next_stage_until_all_nodes_in_stage_terminal` 中的 `Event.timestamp` 排序断言改为 `Event.seq`
- [x] 1.3 审查 `tests/yaml_dsl/test_yaml_dsl_workflow.py` 其余 timestamp 排序断言并统一（本文件已无 `.timestamp` 排序断言）

## 2. Verification

- [x] 2.1 运行相关 pytest（与 sleep-fixtures 一并验证 pipeline overlap）
- [x] 2.2 `llman sdd validate c0-fix-timestamp-test-assertions --strict --no-interactive`
