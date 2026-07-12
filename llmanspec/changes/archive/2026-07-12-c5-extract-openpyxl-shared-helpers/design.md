# Design: extract-openpyxl-shared-helpers

## 目标

消除 openpyxl write 辅助在 `workflow` / `sinks` 的平行副本，并避免 `_internal.utils` 反向依赖 `sinks`。

## 方案

1. **`_internal/utils/atomic_paths.py`**：迁入原子临时路径 SSOT（原 `sinks._internal.base` 实现）。
2. **`_internal/utils/openpyxl_helpers.py`**：
   - `best_effort_close_write_only_worksheet`
   - `best_effort_close_write_only_workbook_worksheets`
   - `save_openpyxl_workbook_atomic`（抛出原始异常；领域错误由调用方包装）
3. **调用点**：
   - `resources_workbook` / `resources_sheetbook`：薄包装保留 `ScalimWorkflowWriteError` 文案
   - `sinks/_internal/excel.py`：close helpers 改为导入别名（测试仍可通过 `excel_mod._best_effort_*`）
   - `base.py`：re-export atomic path 符号，兼容既有导入

## 非目标

- 不改变 Excel/workbook/sheetbook 写出语义与公共 API
- 不合并 sinks 内带 logging 的 save 路径（错误消息/日志口径不同）
