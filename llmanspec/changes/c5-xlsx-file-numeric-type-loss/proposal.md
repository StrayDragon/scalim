---
depends_on: []
blocks: []
---

# c5-xlsx-file-numeric-type-loss

## Why

`xlsx_file` book 在 workflow 中经 CSV 中间层 (`InMemoryCsvSink._normalize_csv_value()` → `str(value)`)，
所有 Python 数字类型被字符串化，最终 Excel 数字列表现为文本。
`xlsx_memory` 已走 `InMemoryRows` 保留类型；二者同为 spreadsheet book，中间态选型不应分叉。

### 影响面（复现已确认）

| 数据类型 | xlsx_file (当前) | xlsx_memory (对照) |
|---|---|---|
| `int` / `float` / `Decimal` / `bool` / `None` / 零值 | 全部 `str`（`None`→`''`） | 保留 `FieldValue` |
| 经 `call_by: to_numeric()` 后 | 仍被 stringify | 保留 |

外部项目需 `_post_process_workbook` 事后修类型。根因是
`managed_artifact_kind` 仅对 `xlsx_memory` 选 ROWS，其余（含 `xlsx_file`）默认 CSV。

### 附带缺陷（同根，本变更一并收口）

1. ROWS plan 仍急切 `to_csv_artifact()`，xlsx_memory 已付约 1.5× 额外内存。
2. `xlsx_file` 中间态不可被 `book_sheet_rows` 读取（写后即死胡同）。
3. workbook 后端仍绑定 `WorkflowCsvInput` + commit 时再读源，与 sheetbook「write 时物化 typed rows」模型不一致。

## What Changes

### 终态原则（内部一步到位；用户 YAML 不变）

1. **Spreadsheet book → typed ROWS**：`xlsx_file` 与 `xlsx_memory` 的 workflow-managed output 一律 `MANAGED_ARTIFACT_KIND_ROWS` + `OutputSpec.format=excel`。
2. **ROWS 不急切复制 CSV**：`_collect_managed_artifact_outputs` 对 ROWS 不调用 `to_csv_artifact()`；`in_memory_rows_to_in_memory_csv` 仅作显式工具保留。按 consumer 自动派生 CSV **不在本变更**（见 `llmanspec/futures/xlsx-file-numeric-type-loss/future.md`）。
3. **Write 一律 tabular**：books 的 `xlsx*`（含 legacy IR `resource_type=workbook`）经 `resolve_workflow_input_tabular()`。
4. **Workbook 与 sheetbook 同构内部模型**：write 时用 `read_tabular_header` / `materialize_aligned_tabular_rows` 物化 `List[List[FieldValue]]` 进 segment（含 `producer_node_id`）；commit 只扫自有 rows；**不保留** CSV 引用旁路、**不**双字段 `input_csv`+`input_tabular`。
5. **`book_sheet_rows` 支持 `xlsx_file`**：可见性/截断语义对齐 sheetbook；返回 typed `FieldValue` rows。

### 用户级兼容

- **零 YAML DSL 变更**（`resources.books.*.xlsx_file` authoring 不变）。
- `apply_book_sheet` / `apply_book_append` 继续接受已有的 `WorkflowTabularInput`（含 `InMemoryCsv` / path，用于非 workflow-managed 与既有测试）。
- 输出从「全 str cell」变为 typed cell：视为 **bug fix**，非功能回退；依赖 str 类型的下游需适配。

### 明确不做

- 不引入启发式 `_auto_cast` / commit 边界猜类型。
- 不引入 output bypass / 非托管写盘逃生口。
- 不新增 YAML book kind；不合并 `resources_workbook.py` 与 `resources_sheetbook.py` 为单文件（可共享小 helper）。
- 不实现「有 CSV consumer 时从 ROWS 自动派生 CSV」（停急切副本 ≠ 已做按需派生）。

延后项与风险表: `llmanspec/futures/xlsx-file-numeric-type-loss/future.md`。

## Capabilities

- `workflow-shared-output-containers`（xlsx_file typed 管道 + workbook 物化模型 + ROWS 无急切 CSV）
- `workflow-managed-temp-outputs`（typed managed artifact 覆盖全部 xlsx\* book consumer）
- `yaml-dsl-books-resources`（`book_sheet_rows` 扩展至 `xlsx_file`）

## Impact

- **代码区域**: `output_composition_yaml.py`, `run_ir.py`, `write_nodes.py`, `resources.py`, `resources_workbook.py`, `loaders`/`book_sheet_rows` 路由, 相关 tests
- **破坏性**: 无 YAML 破坏；xlsx_file 导出 cell 的 Python 类型从 str→typed（修复）
- **内存**: 去掉 ROWS→CSV 急切副本（xlsx_memory 约省 60% 峰值）；xlsx_file write 时物化一份 typed rows（与 sheetbook 同模型，换正确性与可读性）
- **MVP**: `examples/numeric-type-loss/run.py`（多 sheet + 单 sheet；xlsx_file 与 xlsx_memory 对照）
