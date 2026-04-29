## 1. Module Split

- [x] 1.1 新增 `src/scalim/dsl/yaml_dsl/_internal/workflow_compile_options.py` 并迁移 options 相关函数(保持签名不变): `_normalize_and_validate_workflow_execution_options`、`_build_workflow_cache_pool_ir_from_runtime`、`_normalize_and_validate_workflow_runtime_options`、`_parse_workflow_option_finite_number`、`_validate_workflow_resources_wait_override`、`_build_workflow_resources_wait_ir`、`_normalize_workflow_output_staging_override`、`_build_workflow_output_staging_ir`、`_build_workflow_options_ir`
- [x] 1.2 新增 `.../_internal/workflow_compile_graph.py` 并迁移 DAG 构建函数: `_build_demand_nodes_and_graph`
- [x] 1.3 新增 `.../_internal/workflow_compile_resources.py` 并迁移 resources/patch 相关函数: `_apply_book_*`、`_apply_file_*`、`_book_override_to_patch`、`_file_override_to_patch`、`_book_export_path_and_options`、`_file_export_path_and_options`、`_compile_workflow_resources`
- [x] 1.4 新增 `.../_internal/workflow_compile_outputs.py` 并迁移 outputs/write-node 相关函数: `_load_demands`、`_effective_outputs_for_workflow_compile`、`_parse_output_extra_sheet_override`、`_apply_overrides_output_extras`、`_parse_overrides_outputs_defaults_book_id`、`_apply_default_book_binding_to_outputs`、`_build_write_node_for_book`、`_append_write_nodes_from_runs`、`_inject_xlsx_memory_write_dependencies`
- [x] 1.5 将 `workflow_compile.py` 收敛为 orchestrator glue: 仅保留 `compile_workflow_ir` + 必要薄封装/常量,并改为从 `_internal/*` 导入实现;补齐模块级 docstring 标注阶段边界(纯规则/IO/runtime options)
- [x] 1.6 约束与验收: 拆分后 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 不再需要 `# pragma: allow-c901-file ...`(或将该 pragma 移到仍然复杂的子模块中),并确保依赖方向不出现环

## 2. Tests

- [x] 2.1 为 `_parse_workflow_option_finite_number` 新增 unit tests(类型/范围校验;不依赖 YAML 文件 IO)
- [x] 2.2 为 `_validate_excel_sheet_name` 或 write-defaults enum 校验新增 unit tests(断言错误信息与 path)
- [x] 2.3 确保现有 workflow compile 集成测试保持通过

## 3. Verification

- [x] 3.1 运行 `just qa`
- [x] 3.2 运行 `just openspec-check`
