# tasks: c5-xlsx-file-numeric-type-loss

内部一步到位（无双轨过渡）。用户 YAML 不变。

## 1. Artifact 决策：xlsx* → ROWS + format=excel

**文件**: `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py`

- 将 `managed_artifact_kind` 分支改为：`book.kind in {"xlsx_memory", "xlsx_file"}` → `MANAGED_ARTIFACT_KIND_ROWS` 且 `OutputSpec(format="excel", ...)`（整段进入 ROWS 分支，不是只改 kind 字符串却留 `format=csv`）。
- 语义注释：spreadsheet book → ROWS。

**验收**: 编译含 `xlsx_file` 的 workflow-managed output 时 plan kind 为 ROWS。

- [ ] 1.1 切换 xlsx_file 到 ROWS + excel OutputSpec
- [ ] 1.2 补充/更新编译侧单测（若有）

## 2. Collect：ROWS 不急切 CSV 副本

**文件**: `src/scalim/execution/run_ir.py` → `_collect_managed_artifact_outputs`

```text
if plan_obj.kind != MANAGED_ARTIFACT_KIND_ROWS:
    csv_artifact = plan_obj.to_csv_artifact()
    ...
```

**验收**: xlsx_memory / xlsx_file managed 路径不发布对应 output 的 CSV 副本；csv_file 路径不变。
**非目标**: 不在此任务实现「按 CSV consumer 自动派生」——见 `llmanspec/futures/xlsx-file-numeric-type-loss/future.md`。

- [ ] 2.1 跳过 ROWS 的 `to_csv_artifact()`
- [ ] 2.2 回归：仅 CSV plan 仍产出 csv map
- [ ] 2.3 确认 `in_memory_rows_to_in_memory_csv` 仍可从 `scalim.sinks.rows` 导入（显式工具保留，collect 不调用）

## 3. Write 路由：xlsx* + legacy workbook → tabular

**文件**: `src/scalim/workflow/write_nodes.py`

- `book` + xlsx kind → `resolve_workflow_input_tabular`
- legacy `resource_type == "workbook"` → 同样 tabular（一步到位）
- 抽取 `is_xlsx_spreadsheet_book_kind`（或等价）避免字面量漂移

**验收**: ROWS-only artifact（无 csv map）时 xlsx_file / legacy workbook write 成功。

- [ ] 3.1 write_sheet / append_sheet book 分支
- [ ] 3.2 legacy workbook 分支改 tabular
- [ ] 3.3 helper + 单测

## 4. Workbook 终态：物化 typed segments（对齐 sheetbook）

**文件**: `src/scalim/workflow/resources_workbook.py`

- 去掉对 `resources_csv._read_csv_header` / `_iter_csv_rows` / `WorkflowCsvInput` 作为 SSOT 的依赖。
- Segment 改为：`producer_node_id`, `decl_order`, `rows: List[List[FieldValue]]`, `header_policy`。
- `apply_workbook_sheet` / `apply_workbook_append`：入参 `WorkflowTabularInput`；`read_tabular_header` + `build_alignment_mapping` + mismatch 策略 + `materialize_aligned_tabular_rows`。
- commit / `_iter_workbook_sheet_rows`：只扫自有 `segment.rows` + `escape_excel_formula`（仅 str）。
- **禁止**双字段旁路；**禁止**为 header 整表 `rows→csv`。

**验收**: `InMemoryRows` 写入后 openpyxl cell 为 typed；既有 `InMemoryCsv` 单测仍通过；duplicate display header 回归仍绿。

- [ ] 4.1 重写 segment / sheet plan 模型
- [ ] 4.2 apply_workbook_sheet 物化路径
- [ ] 4.3 apply_workbook_append 物化路径（含 mismatch）
- [ ] 4.4 commit 写出 typed rows
- [ ] 4.5 更新 `tests/workflow/test_workflow_resources_coverage.py` 等直接测 workbook 的用例

## 5. Facade：放开 Rows + book_sheet_rows(xlsx_file)

**文件**: `src/scalim/workflow/resources.py`（及 sheet 迭代实现）

- 删除 `_require_csv_input` 对 `InMemoryRows` 的拒绝（可删除该 helper 若已无引用）。
- `iter_book_sheet_rows`：允许 `xlsx_file`；实现截断/可见性与 sheetbook 同契约（可抽共享可见性 helper，或 workbook 侧镜像实现）。
- 更新错误文案（不再写 only supports xlsx_memory）。

**验收**: loader `book_sheet_rows` 读 xlsx_file sheet 返回 typed dict rows；越界可见性 fail-fast。

- [ ] 5.1 放开 apply_book_* 对 Rows
- [ ] 5.2 iter_book_sheet_rows 支持 xlsx_file
- [ ] 5.3 单测：xlsx_file book_sheet_rows + 可见性

## 6. 集成 / MVP / 门禁

- [ ] 6.1 `uv run python3 llmanspec/changes/c5-xlsx-file-numeric-type-loss/examples/numeric-type-loss/run.py` — 场景 A/B 的 xlsx_file 类型丢失为 0
- [ ] 6.2 `uv run pytest -x -q tests/workflow tests/yaml_dsl`（或全量 `tests/`）
- [ ] 6.3 `llman sdd validate c5-xlsx-file-numeric-type-loss --strict --no-interactive`
- [ ] 6.4 `just qa`（若环境允许）

## 实现顺序建议

`2` 可先于或并行于 `1`（xlsx_memory 立即受益）；`1→3→4→5` 有依赖；`6` 收尾。
