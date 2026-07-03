# Design — c10-fix-duplicate-display-headers

## 根因与修复层次

### 根因(源头)

workflow 的 `xlsx_file`(workbook) 与 `csv`(file) 路径,`workflow-managed` 中间工件 `InMemoryCsv` 的 `header` = 展示名(可重复)。写入节点 `_build_alignment_mapping(header, header)` 按列名 `Dict` 去重 → 重复名坍缩到首现 → 数据错位。

对照 `xlsx_memory`(sheetbook) 不受影响: 中间工件 `InMemoryRows.header` = `field_id`(唯一),展示名经独立 `export_header` 仅用于表头行。

### 方法对比

| 方法 | 范围 | append 乱序重复名 | 评价 |
|---|---|---|---|
| B. 仅 identity patch | 极小 | ❌ 仍坍缩 | patch,不彻底 |
| **A. 源头对齐统一(采纳)** | 中(5 模块,每处小且对称) | ✅ 安全 | 消除根因,三路径统一 |
| C. A + identity patch(最终方案) | 中 | ✅ 安全 | 源头为主 + identity 作通用语义自洽修正与次要防御 |

**采纳 C**: 源头对齐消除根因,identity 快速路径(已实施)保留为 `_build_alignment_mapping` 的通用语义自洽修正——`expected==actual` 时位置恒等本就是该函数的正确语义,且作为 future 重复名 input 的次要防御。

## 源头修复设计(elegant 统一)

### 核心改动:一行条件(`output_composition_yaml.py`)

当前两处(direct targets + derived targets):
```python
if in_memory and book is not None and str(book.kind or "").strip() == "xlsx_memory":
    export_layout = export_layout_from_demand_ir(..., header_fields_output_by=str(header_by))
    workflow_export_header = _rendered_header_row(export_layout)
    layout_header_by = "field_id"
```
改为:
```python
if in_memory:
    export_layout = export_layout_from_demand_ir(..., header_fields_output_by=str(header_by))
    workflow_export_header = _rendered_header_row(export_layout)
    layout_header_by = "field_id"
```
**效果**: 所有 `in_memory` 工件(book 的 xlsx_file/xlsx_memory + file 的 csv)`InMemoryCsv.header`/`InMemoryRows.header` = `field_id`;展示名经 `workflow_export_header` 独立透传。非 in_memory 路径(demand 直写文件)不受影响(`in_memory=False`,sink 按 field_id 取值,展示名写表头——本就正确)。

### export_header 透传(workbook/csv 复刻 sheetbook 模式)

`sheetbook` 已有 `export_header` 参数 + `_SheetBookSheetPlan.export_header` + 表头写 `export_header`。workbook/csv 当前缺失,复刻之:

- `write_nodes.py`: workbook(`book`)与 csv(`file`)路径调 `resolve_workflow_output_export_header` 并透传(已有的 sheetbook 路径同样如此)。
- `resources.py`: `apply_book_sheet`/`apply_book_append` 增加 `export_header` 参数并转发给 `apply_workbook_*`。
- `resources_workbook.py`: `_SheetPlan` 增加 `export_header: Optional[List[str]]`;`apply_workbook_sheet`/`apply_workbook_append` 接收+存储;`_iter_workbook_sheet_rows` 表头行写 `export_header`(对齐仍用 `baseline_header=field_id`)。
- `resources_csv.py`: `_CsvPlan` 增加 `export_header: Optional[List[str]]`;`apply_csv_append` 接收+存储;`_commit_csv` 表头行写 `export_header`。

### 对齐语义(修复后)

- `baseline_header` = `field_id`(首次写入时由 `input_header` 设置,修复后 `input_header=field_id`)。
- `_build_alignment_mapping(field_id, field_id)` = identity(不坍缩);append 乱序时按 `field_id` 名正确匹配。
- 表头行 = `export_header`(展示名,可重复)。
- 输出文件(xlsx/csv)表头 = 展示名(与修复前一致),数据 = 按 field_id 正确对齐(修复后正确)。**对下游消费者无表面变化,仅数据正确性修复**。

### `align_by` 处理

修复后工件 `header=field_id`,`align_by=header` 与 `align_by=field_id` 内部等价(都按 field_id 对齐)。**保留 `align_by` 选项不变**(不 breaking,内部等价);不引入 sheetbook 式的 `align_by=header` 禁止(demo 在用,且修复后无害)。

## 文档/生成边界

- 本变更无生成物/注入区块(不触发 `just gen-docs`)。
- 行为 SSOT: `llmanspec/specs/workflow-shared-output-containers/spec.toon`(delta 合入后)。
- drift gate: `just qa`。

## MVP 例子

`llmanspec/changes/c10-fix-duplicate-display-headers/examples/duplicate-display-headers/`: 独立可运行目录(demand.yaml + workflow.yaml + data_loader.py + run.py + README.md),覆盖 xlsx_file/xlsx_memory/csv 三路径,脱敏占位数据,验证重复展示名下数据不错位。
