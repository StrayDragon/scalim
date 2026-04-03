## Why

`run_workflow(...)` 当前会在 workflow IR 编译阶段预加载所有 demand YAML，但这一步仍默认执行 `validate_unique_field_names=True`。由于 `validate_unique_field_names` 已迁移到 runtime entrypoint / per-run patch 控制面，阶段 1 的 fail-fast 与现有 runtime policy 边界冲突，导致用户无法通过 `demand_diagnostics` 或 `run_patches_by_id` 绕过 intentional duplicate display names 的 demand。

## What Changes

- 调整 workflow compile 阶段的 demand 预加载语义：`compile_workflow_ir()` / `_load_demands()` 仅做结构加载，不再提前执行 `validate_unique_field_names`。
- 保持 duplicate display name 诊断在 demand runtime compile 阶段生效，由 `compiler.compile()` 继续根据全局 `DemandDiagnosticsPolicy` 和 per-run `DemandDiagnosticsOverride` 决定是否校验。
- 为 workflow compile、`run_workflow(..., demand_diagnostics=...)`、`run_patches_by_id` 补充回归测试，覆盖 duplicate display names 场景。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `yaml-dsl-runtime-policy-boundary`: 明确 workflow compile 预加载 demand 时不得抢跑 `validate_unique_field_names` 这类 runtime diagnostics policy。
- `workflow-run-patches`: 明确 per-run `demand_diagnostics` override 不能被 workflow compile 阶段的 demand 预加载绕过。
- `yaml-dsl-workflow`: 明确 workflow demand 预加载仅用于结构分析，不应在运行前提前执行 runtime-only duplicate field-name diagnostics。

## Impact

- 受影响代码：`src/scalim/dsl/by_yaml/workflow_compile.py`、`src/scalim/dsl/by_yaml/workflow_entrypoints.py`、workflow 相关测试。
- 受影响 API：`run_workflow(...)` / `compile_workflow_ir(...)` 的行为边界更一致，但不引入新的用户侧 authoring surface。
- 不涉及生成物或注入区块；OpenSpec SSOT 为本 change 下工件和对应的 main specs。
