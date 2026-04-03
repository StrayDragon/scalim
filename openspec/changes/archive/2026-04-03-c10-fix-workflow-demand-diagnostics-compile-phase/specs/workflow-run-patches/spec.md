## ADDED Requirements

### Requirement: per-run demand diagnostics overrides MUST survive workflow compile preloading

当 `run_workflow(...)` 提供 `run_patches_by_id[*].demand_diagnostics` 时，系统 MUST 保证这些 per-run diagnostics override 不会被 workflow compile 阶段的 demand 预加载抢跑绕过。

#### Scenario: per-run duplicate-name suppression applies after workflow compile
- **GIVEN** workflow 中 run `A` 引用的 demand YAML 含有 duplicate effective field display names
- **AND** 调用方传入 `run_patches_by_id={"A": WorkflowRunPatch(demand_diagnostics=DemandDiagnosticsOverride(validate_unique_field_names=False))}`
- **WHEN** 系统执行 `run_workflow(...)`
- **THEN** workflow compile 阶段 MUST 成功完成 demand 预加载
- **AND** run `A` 的后续 demand compile MUST 使用该 per-run override
- **AND** 系统 MUST NOT 因阶段 1 的默认 duplicate-name 校验提前失败
