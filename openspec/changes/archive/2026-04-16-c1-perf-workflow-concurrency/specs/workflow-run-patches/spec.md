# workflow-run-patches (delta) Specification

## ADDED Requirements

### Requirement: per-run patches MUST support parallel_mode and max_workers overrides
`run_workflow(..., run_options_patches_by_run_id=...)` 的 per-run patch MUST 支持覆盖并发相关 runtime knobs，使同一 workflow 内不同 run 可采用差异化策略：

- `parallel_mode` MUST 支持 `seq|adaptive`（其余值 MUST fail-fast）
- `max_workers` MUST 支持非负整数（`0=auto`）；负数或非整数 MUST fail-fast
- 当 per-run patch 未显式提供上述字段时 MUST 继承全局 `RunOptions` 的对应值
- per-run patch 的该类覆盖 MUST 仍遵循既有安全边界：不得覆盖 `allowed_modules/allowed_functions/resolver_trusted_mode`

#### Scenario: per-run parallel_mode overrides global parallel_mode
- **GIVEN** 全局 `RunOptions.parallel_mode="seq"`
- **WHEN** 调用 `run_workflow(..., run_options_patches_by_run_id={"A": WorkflowRunOptionsPatch(parallel_mode="adaptive")})`
- **THEN** run `A` 的 effective `parallel_mode` MUST 为 `"adaptive"`

#### Scenario: per-run max_workers overrides global max_workers
- **GIVEN** 全局 `RunOptions.max_workers=0`（auto）
- **WHEN** 调用 `run_workflow(..., run_options_patches_by_run_id={"A": WorkflowRunOptionsPatch(max_workers=4)})`
- **THEN** run `A` 的 effective `max_workers` MUST 为 `4`

#### Scenario: invalid per-run parallelism knobs are rejected
- **WHEN** 用户提供 `WorkflowRunOptionsPatch(parallel_mode="thread")` 或 `WorkflowRunOptionsPatch(max_workers=-1)`
- **THEN** `run_workflow` MUST fail-fast
- **AND** 错误信息 MUST 指出合法值范围（`parallel_mode=seq|adaptive`, `max_workers>=0`）

