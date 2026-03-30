<!--
本文件用于记录 `c2-tests-domain-suites` 的迁移前基线与调研结果。
变更落地后本文件会随 change 一同归档,作为“迁移前后对拍”的审计依据。
-->

# Inventory / Baseline

Date: 2026-03-30

## 1) tests/ 规模概览（迁移前）

- Top-level `tests/test_*.py` files: **202**
- `pytest --collect-only --no-cov`: **2268/2289 collected** (21 deselected, bench)
- `just test`: **PASS** (2268 passed, cov=100.00%)

### 1.1 文件名前缀分布（按 `test_<prefix>_*.py`）

- `yaml`: 65
- `workflow`: 16
- `sinks`: 8
- `execution`: 8
- `planning`: 8
- `executor`: 7
- `output`: 5
- `adaptive`: 4
- `hooks`: 4
- 其它：若干

### 1.2 marker 分布

- `tests/bench/`: 5 files (bench suite)
- `pytest.mark.bench`: 5 files
- `pytest.mark.slow`: 3 files

### 1.3 Top 20 超大文件（按行数）

1. `tests/test_yaml_dsl_workflow.py` (4509)
2. `tests/test_workflow_resources_coverage.py` (2262)
3. `tests/test_executor_operator_load_ref.py` (1338)
4. `tests/test_yaml_parser_outputs_internal.py` (1148)
5. `tests/test_yaml_dsl_imports.py` (973)
6. `tests/test_execution_internal.py` (892)
7. `tests/test_viz_hook.py` (859)
8. `tests/test_output_composition.py` (845)
9. `tests/test_workflow_execute_extra_coverage.py` (831)
10. `tests/test_observer.py` (769)
11. `tests/test_adaptive_execution_tuning.py` (766)
12. `tests/test_preload_cache.py` (746)
13. `tests/test_yaml_validator_edges.py` (725)
14. `tests/test_yaml_source_normalize.py` (696)
15. `tests/test_yaml_overlay.py` (682)
16. `tests/test_execution.py` (660)
17. `tests/test_yaml_runner.py` (641)
18. `tests/test_yaml_template_vars_precompile.py` (609)
19. `tests/test_yaml_workflow_compile_books_io_coverage.py` (601)
20. `tests/test_yaml_runtime_output_composition_yaml_internal.py` (601)

## 2) YAML/配置中的字符串引用入口（迁移前）

### 2.1 YAML 夹具中的 `loader:`/`call_by:` 字符串引用（发现）

- `tests/fixtures/yaml_dsl_validation_refactor.yaml`
  - `loader: tests.conftest.mock_loader`

### 2.2 Python 测试中的 `allowed_modules` / `loader` / `call_by` 字符串引用（高频）

当前高频引用点集中在：

- `tests.conftest.mock_loader`（大量 YAML snippet / dict config / `MainSourceConfig.loader`）
- `allowed_modules=frozenset(["tests.conftest"])`
- `allowed_modules=frozenset(["tests.call_by_fns"])`
- `allowed_modules=frozenset(["tests.params_template_loaders"])`
- `allowed_modules=frozenset(["tests.source_normalize_loaders", "tests.source_normalize_call_by"])`
- `allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"])`
- `allowed_modules=frozenset(["tests.resolver_allowlist_mod"])`
- 已在稳定边界内（无需迁移）：`tests.fixtures.workflow_loaders`、`tests.fixtures.yaml_outputs_e2e`

结论（用于 Task 2.3）：

- **可移动**：以上所有 `tests.*` 字符串引用入口都应一次性迁移/重写到 `tests.fixtures.*`（不保留旧路径兼容）。
- **不可移动/需谨慎**：`tests/conftest.py` 作为 pytest fixture 入口可以保留，但其符号不得再作为 `loader:`/`call_by:` 字符串引用入口。

## 3) 重复热点（迁移前）

### 3.1 `*_additional.py`

共 7 个：

- `tests/test_output_composition_additional.py`
- `tests/test_run_ir_additional.py`
- `tests/test_sinks_additional.py`
- `tests/test_sinks_excel_additional.py`
- `tests/test_yaml_app_additional.py`
- `tests/test_yaml_converter_additional.py`
- `tests/test_yaml_validator_additional.py`

### 3.2 `*_coverage.py`

共 7 个：

- `tests/test_workflow_capture_replay_coverage.py`
- `tests/test_workflow_config_validation_coverage.py`
- `tests/test_workflow_execute_extra_coverage.py`
- `tests/test_workflow_resources_coverage.py`
- `tests/test_yaml_loader_books_io_coverage.py`
- `tests/test_yaml_runtime_compiler_io_overrides_coverage.py`
- `tests/test_yaml_workflow_compile_books_io_coverage.py`
