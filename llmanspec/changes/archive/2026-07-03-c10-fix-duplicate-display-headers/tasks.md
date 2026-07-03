# Tasks — c10-fix-duplicate-display-headers

## 已完成: identity 快速路径(通用语义自洽修正 + 次要防御)

- [x] 1. 实现: 在 `src/scalim/workflow/resources_csv.py` 的 `_build_alignment_mapping` 增加 identity 快速路径(当 `expected` 与 `actual` 为同一序列时返回 `list(range(len(expected)))`),并在模块内复用该判定的辅助(避免重复实现)。
- [x] 2. 翻转 `tests/workflow/test_workflow_duplicate_display_headers_regression.py`: 移除 2 个 `@pytest.mark.xfail(...)` 标记,使 `test_build_alignment_mapping_collapses_duplicate_display_headers` 与 `test_workbook_sheet_duplicate_display_headers_corrupts_exported_xlsx` 成为正常通过用例(并按修复后语义调整断言/命名,移除“collapses/corrupts”措辞)。
- [x] 3. 补充单元测试覆盖 identity 快速路径边界: 空 header、单列、全重复名、expected 与 actual 长度不同时维持现有列名匹配回退。

## 源头对齐统一(主修复)

- [x] 4. `output_composition_yaml.py`: 将两处 `if in_memory and book is not None and str(book.kind or "").strip() == "xlsx_memory":` 改为 `if in_memory:`,使所有 in_memory 工件(book 的 xlsx_file/xlsx_memory + file 的 csv)统一 `layout_header_by="field_id"` + 设置 `workflow_export_header`。
- [x] 5. `write_nodes.py`: workbook(`book`)路径的 `apply_book_sheet`/`apply_book_append` 调用与 csv(`file`)路径的 `apply_csv_append` 调用,透传 `export_header=_resolve_workflow_output_export_header(...)`(复刻已有 sheetbook 路径)。
- [x] 6. `resources.py`: `apply_book_sheet`/`apply_book_append` 增加 `export_header: Optional[Tuple[str, ...]] = None` 参数并转发给 `apply_workbook_sheet`/`apply_workbook_append`。
- [x] 7. `resources_workbook.py`: `_SheetPlan` 增加 `export_header: Optional[List[str]] = None`;`apply_workbook_sheet`/`apply_workbook_append` 接收+存储 `export_header`(复刻 sheetbook `_SheetBookSheetPlan` 模式);`_iter_workbook_sheet_rows` 表头行写 `export_header`(对齐仍用 `baseline_header`)。
- [x] 8. `resources_csv.py`: `_CsvPlan` 增加 `export_header: Optional[List[str]] = None`;`apply_csv_append` 接收+存储 `export_header`;`_commit_csv` 表头行写 `export_header`(对齐仍用 `baseline_header`)。
- [x] 9. 创建 MVP 例子 `llmanspec/changes/c10-fix-duplicate-display-headers/examples/duplicate-display-headers/`: `demand.yaml`(重复展示名字段 + `header_fields_output_by: name`)+ `workflow.yaml`(xlsx_file + xlsx_memory + csv 三 book)+ `data_loader.py`(内存 loader,脱敏占位数据)+ `run.py`(独立运行入口)+ `README.md`(场景/运行/期望输出对比)。
- [x] 10. 更新/扩展 `tests/workflow/test_workflow_duplicate_display_headers_regression.py`: 补充源头修复验证(中间工件 header=field_id、export_header 独立、append 乱序重复名不坍缩)。

## 校验

- [x] 11. 校验(增量):
  - `uv run pytest tests/workflow/test_workflow_duplicate_display_headers_regression.py -o addopts="" -q`
  - `uv run pytest tests/workflow/ -o addopts="" -q`
  - `uv run ruff check <changed files>`
  - `uv run ruff format --check <changed files>`
- [x] 12. MVP 独立运行: `uv run python llmanspec/changes/c10-fix-duplicate-display-headers/examples/duplicate-display-headers/run.py`(验证三路径输出数据不错位)。
- [x] 13. llmanspec 校验: `llman sdd validate c10-fix-duplicate-display-headers --strict --no-interactive`
- [x] 14. 全量质量门: `just check-only-py` + `just examples`(`just frontend-check` 的 npm audit 为预存在独立事项)
- [x] 15. 归档准备(实现完成后): 使用 `llman-sdd-archive` 将本变更归档并合入 `llmanspec/specs/workflow-shared-output-containers/spec.toon`。
