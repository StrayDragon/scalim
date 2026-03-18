## 1. 运行期预检查落地

- [x] 1.1 在 `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py` 将 workbook reserved/collision 检测从 `_compile_workflow_ir()` 静态全量扫描迁移到“node compile 前”的运行期路径。
- [x] 1.2 为 `{$init_var: ...}` 与 `$ctx` 渲染后的 `init_vars` 路径解析实现统一的解析函数（优先复用 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py` 的解析逻辑，避免重复/漂移）。
- [x] 1.3 确保 reserved-path 判定与 collision 判定均基于“最终解析的绝对路径”，并在错误中输出 `run_id`、path 与冲突 nodes。

## 2. 测试与回归护栏

- [x] 2.1 新增 workflow 测试：两个 runs 的 `outputs.container.path={$init_var: output_path}`，分别注入不同 path → MUST 不误报 collision。
- [x] 2.2 新增 workflow 测试：两个 runs 解析后命中同一路径（通过 init_vars 或 $ctx）→ MUST fail-fast 且错误包含最终 path 与 nodes。
- [x] 2.3 新增 workflow 测试：workflow resources 声明 `sheetbooks.*.export_xlsx.path`，demand 输出解析后命中该路径 → MUST fail-fast（reserved）。

## 3. 规范同步与门禁

- [x] 3.1 更新增量规范 `openspec/changes/c10-workflow-dynamic-path-precheck/specs/workflow-sheetbook-resources/spec.md`，补齐动态路径场景的可测试 Scenario。
- [x] 3.2 运行 `just openspec-check` 确保 OpenSpec 工件结构与脱敏规则通过。
- [x] 3.3 运行 `just qa`（或至少覆盖 workflow 相关单测）确保无回归。
