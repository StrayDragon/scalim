## 1. Workflow compile boundary

- [x] 1.1 调整 `src/scalim/dsl/by_yaml/workflow_compile.py` 的 demand 预加载逻辑，使 workflow IR compile 固定跳过 `validate_unique_field_names` 这类 runtime-only diagnostics。
- [x] 1.2 确认 `src/scalim/dsl/by_yaml/workflow_entrypoints.py` 与 runtime compiler 的现有 effective diagnostics 合并语义保持不变，不新增兼容分支或新 entrypoint 参数。

## 2. Regression coverage

- [x] 2.1 在 `tests/yaml_dsl/` 增加 workflow compile 回归测试，验证 duplicate display names demand 不会在 `compile_workflow_ir(...)` 阶段提前失败。
- [x] 2.2 在 `tests/yaml_dsl/` 增加 workflow run 回归测试，分别覆盖全局 `DemandDiagnosticsPolicy(validate_unique_field_names=False)` 和 per-run `WorkflowRunPatch(...DemandDiagnosticsOverride(validate_unique_field_names=False))`。
- [x] 2.3 扩展用户侧 notebook / public API gate，使 `run_workflow(...)` 的 duplicate display names 抑制路径在真实示例入口中被覆盖。

## 3. Spec and validation

- [x] 3.1 维护本 change 下的 OpenSpec 工件作为 SSOT；本次不修改任何 `.gen.` / injected-block 文件，因此无需运行 `just gen-docs`。
- [x] 3.2 运行针对性 pytest（含 `tests/public_api/` notebook gate）与 `openspec validate --all --strict --no-interactive`（或 `just openspec-check`）作为验收，确认实现与 spec 无漂移。
