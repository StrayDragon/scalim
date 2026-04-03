## 1. Runtime policy typed surface

- [ ] 1.1 新增 demand runtime diagnostics policy 数据类(例如 `DemandDiagnosticsPolicy`): 承载 `include_full_error_message`(默认 `false`) 与 `validate_unique_field_names`(默认 `true`)
- [ ] 1.2 `run`/`compile` 入口新增单个参数 `demand_diagnostics: Optional[DemandDiagnosticsPolicy] = None`,并在内部注入到 `RunOptions`
- [ ] 1.3 为 `run_workflow` 的 per-run 覆盖扩展 `src/scalim/dsl/by_yaml/workflow_types.py::WorkflowRunPatch`: 增加 `demand_diagnostics` 补丁字段(需要字段级三态 UNSET merge,避免覆盖全局设置),并在 `src/scalim/dsl/by_yaml/workflow_entrypoints.py::_apply_workflow_run_patch` 透传到 `RunOptions`(不新增额外 patch 参数)
- [ ] 1.4 在 `src/scalim/dsl/by_yaml/runtime/compiler.py::_apply_demand_runtime_policy_overrides` 注入上述两个策略到 `DemandConfig`(维持旧行为,仅改变配置入口)

## 2. YAML mainline fail-fast + schema 收敛

- [ ] 2.1 `src/scalim/dsl/by_yaml/_internal/config_parsing/loader.py`: YAML 顶层出现 `include_full_error_message` / `validate_unique_field_names` 时 fail-fast,并给出迁移提示(改用 runtime entrypoints)
- [ ] 2.2 `src/scalim/dsl/by_yaml/schema_dsl/models/demand.py`: 将 `include_full_error_message` / `validate_unique_field_names` 从 schema SSOT 移除或 `schema_omit()` (YAML stable authoring surface 不再暴露)
- [ ] 2.3 生成物刷新(禁止手改): 运行 `just gen-docs` 以更新 `src/scalim/dsl/by_yaml/schema/*.gen.json` 与 `docs/doc/yaml-dsl/*.gen.md` 等 drift 相关生成物

## 3. 文档与示例迁移

- [ ] 3.1 更新 `docs/doc/yaml-dsl/syntax.md` / `docs/doc/yaml-dsl/user-guide.md` / `docs/doc/yaml-dsl/capability-matrix.md` 等: 移除 YAML 字段,新增 `demand_diagnostics=...` / `run_workflow(..., run_patches_by_id=...)` 的 runtime 参数示例与迁移说明
- [ ] 3.2 更新 repo 内示例 YAML/Notebook fixtures(例如 `notebooks/marimo/...`): 删除 YAML 顶层字段并在 Python 调用侧示例中补齐 runtime 参数

## 4. 测试与验收

- [ ] 4.1 更新/新增单测: YAML 中出现旧字段时应报错且包含迁移提示
- [ ] 4.2 更新/新增单测: runtime policy 开关生效(默认行为不变;显式开启/关闭影响输出 redaction 与 unique-name 预检查)

## 5. OpenSpec / QA gate

- [ ] 5.1 运行 `just openspec-check` 验证本 change 的 delta specs 与 OpenSpec 结构有效
- [ ] 5.2 运行 `just qa` 通过 lint/tests + doc/schema drift gate
