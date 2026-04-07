## MODIFIED Requirements

### Requirement: run_workflow MUST accept per-run patches keyed by workflow run id

`run_workflow(...)` MUST 接受一个可选参数 `run_patches_by_id`,用于按 `workflow.runs[*].id` 注入 per-run runtime patches。

语义:

- `run_patches_by_id` 的 key MUST 等于 `workflow.runs[*].id`
- patch 仅作用于对应的 demand run,不作用于 workflow 内部派生节点(例如 write/append 等)
- per-run patch 的优先级 MUST 高于 `run_workflow(..., options=RunOptions(...))` 提供的全局 runtime knobs

#### Scenario: per-run batch_size overrides the global batch_size

- **WHEN** workflow 定义两个 runs: `A` 与 `B`
- **AND** 调用 `run_workflow(..., options=RunOptions(..., batch_size=2000), run_patches_by_id={"A": WorkflowRunPatch(batch_size=5000)})`
- **THEN** run `A` 的 effective `batch_size` MUST 为 `5000`
- **AND** run `B` 的 effective `batch_size` MUST 为 `2000`
