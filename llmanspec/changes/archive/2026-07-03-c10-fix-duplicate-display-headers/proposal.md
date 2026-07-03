---
depends_on: []
blocks: []
---

# c10-fix-duplicate-display-headers

## Why

用户反馈: workflow 模式导出 `xlsx`/`csv` 时,当用户希望输出的展示列名(给数据同事查看)存在重复(例如多个指标块共用“人数”/“金额”),最终导出的数据行中后续同名列被首列的值填充,造成数据错位。底层输出字段 `field_id` 全局唯一(明确约束),重复仅发生在展示名层。

根因(源头): workflow 的 `xlsx_file`(workbook) 与 `csv`(file) 路径,其 `workflow-managed` 中间工件 `InMemoryCsv` 的 `header` 携带的是**展示名**(可重复),而写入节点用 `_build_alignment_mapping(expected, actual)` 按**列名**建列映射,`Dict` 去重导致重复列名坍缩到首次出现索引 → 数据错位。

对照: `xlsx_memory`(sheetbook) 路径**不受影响** —— 其中间工件 `InMemoryRows` 的 `header` 固定为 `field_id`(唯一),展示名经独立 `export_header` 仅用于表头行。

已通过脱敏 MVP 复现并验证: `tests/workflow/test_workflow_duplicate_display_headers_regression.py` + `llmanspec/changes/c10-fix-duplicate-display-headers/examples/duplicate-display-headers/`。

## What Changes

**核心原则**: 对齐永远基于唯一 `field_id`,展示名只用于表头行。把 `xlsx_memory`/sheetbook 已正确的设计推广到 `xlsx_file`/workbook 与 `csv`/file,三路径统一。

- `output_composition_yaml.py`: 所有 `in_memory` 工件(无论 book/file)统一 `layout_header_by="field_id"` + 设置 `workflow_export_header`(去掉 `book.kind==xlsx_memory` 限制)。**核心一行条件改动**,使 `InMemoryCsv.header=field_id`。
- `write_nodes.py`: workbook(`book`)与 csv(`file`)路径透传 `export_header`。
- `resources.py`: `apply_book_sheet`/`apply_book_append` 转发 `export_header` 给 workbook。
- `resources_workbook.py`: `_SheetPlan` + `apply_workbook_*` + `_iter_workbook_sheet_rows` 接收并使用 `export_header`(表头写 `export_header`,对齐用 `baseline_header=field_id`)——复刻 sheetbook `_SheetBookSheetPlan` 已有模式。
- `resources_csv.py`: `_CsvPlan` + `apply_csv_append` + `_commit_csv` 同理。
- 保留 identity 快速路径(已实施)作为 `_build_alignment_mapping` 的通用语义自洽修正(`expected==actual` 时位置恒等本就是正确语义)+ 次要防御。
- `align_by` 选项保留不变(修复后工件 header=field_id,`align_by=header` 与 `field_id` 内部等价,不 breaking)。

## Capabilities

- `workflow-shared-output-containers`: 新增 `r22`(写入节点按 `field_id` 对齐,展示名仅用于表头行)。

## Impact

- 代码: `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py`、`src/scalim/workflow/write_nodes.py`、`src/scalim/workflow/resources.py`、`src/scalim/workflow/resources_workbook.py`、`src/scalim/workflow/resources_csv.py`。
- 测试: `tests/workflow/test_workflow_duplicate_display_headers_regression.py`(已有,翻转 xfail + 补源头验证)。
- MVP 例子: `llmanspec/changes/c10-fix-duplicate-display-headers/examples/duplicate-display-headers/`(可独立运行,脱敏)。
- 不涉及 docs/specs/skills 生成物或注入区块; 无文档 drift(本变更本身)。
- 不涉及 authoring surface/YAML schema 变更; 无迁移(`align_by`/`header_fields_output_by` 语义不变,仅内部对齐键纠正)。
- SSOT: 行为 SSOT 为 `llmanspec/specs/workflow-shared-output-containers/spec.toon`(delta 合入后); 代码 SSOT 为上述 5 模块。

## Scope Exclusions (Future)

- sink `write_row_aligned`/`write_column_aligned` 的 `{key: i}` 末次覆盖式坍缩硬化(与本次根因同源,当前因 field_id 唯一未触发)记入 `future.md`。
