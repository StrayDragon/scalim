## Context

### 调研: workflow_compile.py 的职责分布(关键路径)

通过扫描 `workflow_compile.py` 的 top-level 函数定义,主要职责块可以清晰分段:

- 资源 patch/overlay 与导出路径解析:
  - `_apply_book_patch/_apply_file_patch`、`_book_override_to_patch/_file_override_to_patch`
  - `_book_export_path_and_options/_file_export_path_and_options`
  - `_compile_workflow_resources`

- workflow DAG 构建:
  - `_build_demand_nodes_and_graph`

- demand YAML 预加载:
  - `_load_demands` (调用 `YamlDemandLoader.load`,含 template_vars/template_sandbox/allowed_yaml_roots)

- outputs 选择与写入节点注入:
  - `_effective_outputs_for_workflow_compile`
  - `_append_write_nodes_from_runs` / `_inject_xlsx_memory_write_dependencies`
  - output_extras/default book binding helpers

- runtime options normalize + IR build:
  - `_normalize_and_validate_workflow_execution_options`
  - `_build_workflow_cache_pool_ir_from_runtime`
  - `_normalize_and_validate_workflow_runtime_options`
  - `_build_workflow_options_ir`

- orchestrator:
  - `compile_workflow_ir`

这些块之间的依赖方向基本是单向的,非常适合拆模块。

## Goals / Non-Goals

Goals:
- 拆分为职责单一的子模块,并在每个子模块顶层 docstring 写清:
  - 输入/输出契约
  - 是否会进行 IO
  - 是否属于 runtime-only policy 边界
- `compile_workflow_ir` 保持为稳定对外入口,其余实现细节下沉到 `_internal`。

Non-Goals:
- 不在本 change 中改变 override/patch 的语义或错误类型(这些由 `c4-dsl-resource-override-ssot` 承担)。

## Decisions

1. 文件布局

推荐布局(示例):
- `src/scalim/dsl/yaml_dsl/workflow_compile.py` 仅保留 orchestrator 与 re-export glue
- `src/scalim/dsl/yaml_dsl/_internal/workflow_compile_resources.py`
- `src/scalim/dsl/yaml_dsl/_internal/workflow_compile_graph.py`
- `src/scalim/dsl/yaml_dsl/_internal/workflow_compile_outputs.py`
- `src/scalim/dsl/yaml_dsl/_internal/workflow_compile_options.py`

2. 函数归属映射(拆分边界更明确)

- `workflow_compile_options.py`:
  - `_normalize_and_validate_workflow_execution_options`
  - `_build_workflow_cache_pool_ir_from_runtime`
  - `_normalize_and_validate_workflow_runtime_options`
  - `_parse_workflow_option_finite_number`
  - `_validate_workflow_resources_wait_override` / `_build_workflow_resources_wait_ir`
  - `_normalize_workflow_output_staging_override` / `_build_workflow_output_staging_ir`
  - `_build_workflow_options_ir`

- `workflow_compile_graph.py`:
  - `_build_demand_nodes_and_graph`

- `workflow_compile_resources.py`:
  - `_apply_book_*` / `_apply_file_*` / `_book_override_to_patch` / `_file_override_to_patch`
  - `_book_export_path_and_options` / `_file_export_path_and_options`
  - `_compile_workflow_resources`

- `workflow_compile_outputs.py`:
  - `_load_demands`(IO;可在模块 docstring 标注“会读文件”)
  - `_effective_outputs_for_workflow_compile`
  - `_parse_output_extra_sheet_override` / `_apply_overrides_output_extras`
  - `_parse_overrides_outputs_defaults_book_id` / `_apply_default_book_binding_to_outputs`
  - `_build_write_node_for_book`
  - `_append_write_nodes_from_runs` / `_inject_xlsx_memory_write_dependencies`

3. 依赖方向
- `_internal/*` 子模块只允许依赖:
  - `schema_dsl/*`、`runtime/contracts.py`、`workflow_types.py`、`workflow_config/*`
  - 以及更底层的 util(例如 `runtime/output_path_resolve.py`)
- orchestrator 模块(`workflow_compile.py`)允许依赖各子模块,但子模块之间应尽量避免环(必要时通过 dataclass/typed payload 打断)。

4. 可测试边界
- 对 extracted rules 增加 unit tests 的顺序:
  - 先为拆出来的纯函数(无 IO)补齐单测
  - 再做搬运(确保无回归)
  - 最后再补充集成级回归(已有测试应覆盖)

## Risks / Trade-offs

- [风险] 大量移动函数导致 import cycle 或相对导入路径出错。
  - 缓解: 拆分时优先按依赖方向分块,并保持 `_internal` 模块低耦合。

- [风险] 纯重构容易引入行为回归。
  - 缓解: 每个迁移阶段都跑 `just qa`;尽量保持函数签名不变,仅移动。

## Migration Plan

- Phase 1: 拆 `workflow_compile_options.py`
- Phase 2: 拆 `workflow_compile_graph.py`
- Phase 3: 拆 `workflow_compile_resources.py`
- Phase 4: 拆 `workflow_compile_outputs.py`

每个 phase 都应是可单独 review 的 patch,且保持 `compile_workflow_ir` 行为不变。

## Open Questions

- 是否要进一步把 `_load_demands` 从 compile 中抽离为“结构预加载”可复用组件? 这可能与 runtime-policy boundary 相关,可后续再开 change。
  - 当前建议: 先在本 change 里保留 `_load_demands` 的位置,仅标注其 IO 属性;等 `c4` 完成后再评估是否抽到更通用的 loader 模块。
