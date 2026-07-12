# Proposal: extract-openpyxl-shared-helpers

## 与 c20/c30 关系

- **不被取代**；对 `c30-workflow-shared-book-memory` 是 **soft 有利前置**（去重 `resources_workbook` / `resources_sheetbook` / excel sink 的 openpyxl helpers），非硬 `depends_on`。
- 与 `c20`（policy/authoring 边界）基本正交。
- 相关归档：`llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`、`.../2026-07-12-c30-workflow-shared-book-memory/`。

## Why

以下 openpyxl 辅助函数在多个文件中重复实现：

1. **`_best_effort_close_write_only_workbook_worksheets`** — 3 份副本:
   - `src/scalim/workflow/resources_workbook.py:39-56`
   - `src/scalim/sinks/_internal/excel.py:111-123`
   - `src/scalim/workflow/resources_sheetbook.py`（导入自 workbook）

2. **`_save_openpyxl_workbook_atomic`** — 2 份副本:
   - `src/scalim/workflow/resources_workbook.py:90-100`（错误消息: "Workbook commit failed"）
   - `src/scalim/workflow/resources_sheetbook.py:118-128`（错误消息: "Sheetbook export failed"）

Bug fix 必须在多处同步修改，存在行为漂移风险。

## What Changes

1. **创建共享模块**: `src/scalim/_internal/utils/openpyxl_helpers.py`
2. **提取函数**:
   - `best_effort_close_write_only_workbook_worksheets(workbook)`
   - `best_effort_close_write_only_worksheet(worksheet)`
   - `save_openpyxl_workbook_atomic(workbook, *, output_path, error_label="Workbook")`
3. **替换所有调用点**: `resources_workbook.py`、`resources_sheetbook.py`、`sinks/_internal/excel.py` 改为导入共享模块
4. **保持公共 re-export**: `resources_workbook.py` 中维持对外导出（兼容已有导入方）

## Capabilities

### Modified Capabilities

- `governance-module-organization` — 消除跨模块重复

## Impact

- **代码区域**: `src/scalim/_internal/utils/`, `src/scalim/workflow/resources_*.py`, `src/scalim/sinks/_internal/excel.py`
- **破坏性**: 无（内部重构，公共 API 不变）
- **可维护性**: 消除 3 处代码重复
