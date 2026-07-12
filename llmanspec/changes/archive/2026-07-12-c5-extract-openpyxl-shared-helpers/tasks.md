# Tasks: extract-openpyxl-shared-helpers

## 1. SSOT 模块

- [x] 1.1 新增 `src/scalim/_internal/utils/atomic_paths.py`
- [x] 1.2 新增 `src/scalim/_internal/utils/openpyxl_helpers.py`
- [x] 1.3 `sinks/_internal/base.py` re-export atomic path 符号

## 2. 调用点替换

- [x] 2.1 `workflow/resources_workbook.py` 使用共享 helpers（保留错误包装与 re-export）
- [x] 2.2 `workflow/resources_sheetbook.py` 使用共享 save helper
- [x] 2.3 `sinks/_internal/excel.py` close helpers 改为导入别名

## 3. 规范与验收

- [x] 3.1 delta `governance-module-organization`（r22/r23）
- [x] 3.2 `llman sdd validate c5-extract-openpyxl-shared-helpers --strict --no-interactive`
- [x] 3.3 `uv run python scripts/check-import-graph.py --check`
- [x] 3.4 相关测试：`tests/sinks/test_sinks_excel_regressions.py`、`tests/workflow/test_workflow_resources_coverage.py`
