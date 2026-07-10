# design: xlsx_file typed 终态（与 sheetbook 同构；无内部双轨）

## 决策摘要

| 决策 | 选择 | 否决 |
|---|---|---|
| 中间态 | `xlsx*` → `InMemoryRows` | CSV 中间 + 事后 cast；新 YAML kind |
| Workbook 内部 | write 时物化 typed rows（对齐 sheetbook） | `input_csv`+`input_tabular` 双字段旁路；commit 再读 CSV 源 |
| CSV 副本 | ROWS 不急切 `to_csv_artifact()` | 双 sink 并行写入 |
| 跨 demand 读 | `book_sheet_rows` 支持 `xlsx_file` | 继续写后死胡同 |
| 用户面 | YAML / books authoring 不变 | output bypass |

**用户级兼容，内部一步到位**：不保留「先旁路再迁移」的过渡实现。

## 终态数据流

```
Demand (workflow-managed, book=xlsx_file|xlsx_memory)
  → InMemoryRowsSink  (FieldValue SSOT)
  → artifacts.in_memory_rows_outputs[output_id]
  → in_memory_csv_outputs 对该 output：不生成

Write node (book kind ∈ {xlsx_file, xlsx_memory}
            或 legacy resource_type ∈ {workbook, sheetbook})
  → resolve_workflow_input_tabular()
  → read_tabular_header(input)
  → materialize_aligned_tabular_rows(...)
  → segment { producer_node_id, decl_order, rows: List[List[FieldValue]], header_policy }
     （xlsx_file / xlsx_memory 同构；不再持有 input_csv 引用）

Commit (xlsx_file)
  → 迭代自有 segment.rows
  → escape_excel_formula(v)  # 仅 str；其余类型透传
  → openpyxl ws.append(typed)

book_sheet_rows(ref={node, book, sheet})  # book 可为 xlsx_file 或 xlsx_memory
  → 按 producer 截断 + 依赖可见性过滤
  → yield Dict[field_id, FieldValue]
```

## 组件契约

### 1. Artifact 决策（`output_composition_yaml`）

```text
if book.kind in {"xlsx_memory", "xlsx_file"}:
    managed_artifact_kind = ROWS
    OutputSpec.format = "excel"
else:
    # 非 book 或未来非 spreadsheet：保持既有 CSV 路径
    ...
```

规则语义：**目标介质是 spreadsheet → ROWS**，不是「是不是 memory」。

### 2. Collect（`run_ir._collect_managed_artifact_outputs`）

**本 change 落地（硬约束）**

- `to_rows_artifact()`：照旧。
- `to_csv_artifact()`：**仅当** `plan.kind != ROWS` 时调用（ROWS 一律跳过）。
- `in_memory_rows_to_in_memory_csv`：**保留**为稳定显式工具（`scalim.sinks.rows`）；**本路径禁止急切调用**。
- 与 `workflow-intermediate-store` r2/r7 对齐（独立 artifact；转换显式、可审计）。

**本 change 不落地（预案 → futures）**

- 「存在 CSV consumer 时自动/按需从 ROWS 派生 CSV」**不做**。
- 当前假设：xlsx\* managed output 的 write consumer 只走 tabular；不依赖 `in_memory_csv_outputs`。
- 若出现「同一 output → xlsx book + csv/file」双消费，按
  `llmanspec/futures/xlsx-file-numeric-type-loss/future.md` 中
  **按 consumer 显式派生 CSV** 升格为独立 change；**禁止**借机恢复无条件急切 `to_csv_artifact()`。

### 3. Write 路由（`write_nodes`）

- `resource_type == "book"` 且 kind ∈ xlsx\* → `resolve_workflow_input_tabular`。
- legacy `resource_type == "workbook"` → 同样 `resolve_workflow_input_tabular`（内部一步到位，不留 CSV-only 孤岛）。
- `sheetbook` 不变（已是 tabular）。
- 抽小 helper（如 `is_xlsx_spreadsheet_book_kind`）避免字面量分叉漂移。

### 4. Workbook 后端（`resources_workbook`）— 终态模型

**删除**对 `WorkflowCsvInput` / `_iter_csv_rows` / `_read_csv_header` 的依赖（workbook 路径）。

Segment 对齐 sheetbook：

```text
WorkbookSegment:
  producer_node_id: str
  decl_order: int
  rows: List[List[FieldValue]]
  header_policy: str
```

`apply_workbook_sheet` / `apply_workbook_append`：

- 入参类型：`WorkflowTabularInput`（`InMemoryRows` | `InMemoryCsv` | CSV path）。
- header / 对齐：`read_tabular_header` + 既有 `build_alignment_mapping` / mismatch 策略（行为与现 CSV 路径等价，值域改为 `FieldValue`）。
- 物化：`materialize_aligned_tabular_rows`；**禁止**为读 header 再整表 `rows→csv`。
- overwrite / append / export_header / field_id 对齐：保持现有语义；仅存储从「源引用」改为「自有 typed rows」。

`_iter_workbook_sheet_rows` / commit 写盘：只扫 `segment.rows` + `escape_excel_formula`（与 sheetbook export 同规则）。

`resources.py`：

- 移除 `_require_csv_input` 对 `InMemoryRows` 的拒绝。
- `iter_book_sheet_rows`：`xlsx_file` 与 `xlsx_memory` 均允许；xlsx_file 走 workbook 上的等价迭代（截断/可见性与 sheetbook 同契约）。

### 5. Decimal / None / bool

- 管道内保持 `FieldValue`（含 `Decimal`）；不得为「好写 Excel」提前 `str` 或盲转 `float`。
- openpyxl 边界之后的文件级 Python round-trip **不承诺**（与 `workflow-sheetbook-resources` r7 口径一致）。
- `None` 不得在中间态变成 `''`；空串仅来自 CSV 适配输入或缺失列填充策略（与 tabular 层现行为一致）。

## 否决项（保留理由）

| 方向 | 理由 |
|---|---|
| Workbook 层字符串猜数字 | `True`/`007`/`None↔''`/Decimal 不可逆；违反 typed SSOT / 反 `_auto_cast` |
| Output bypass | 破坏原子 commit；放大两层架构心智；与本 bug 正交 |
| 双字段旁路 / 渐进双轨 | 把过渡态写进代码与 spec，维护成本高于一次改 workbook 模型 |
| 新 YAML `xlsx_typed` | 违反单主线；用户无收益 |

## 兼容矩阵

| 场景 | 行为 |
|---|---|
| YAML `books.xlsx_file` | 不变 |
| xlsx_file + workflow | cell 类型修复为 typed；可 `book_sheet_rows` |
| xlsx_memory + workflow | 输出不变；去掉急切 CSV 副本 |
| `InMemoryCsv` / CSV path → `apply_workbook_*` | 仍可用（tabular 适配）；值为 str 域 |
| csv_file / files | 不变 |
| standalone xlsx_file | 不经 managed CSV 中间层；本变更不改其主路径语义 |

## 风险分析

完整表与残留升级条件见
`llmanspec/futures/xlsx-file-numeric-type-loss/future.md` § Risk Analysis。
此处只列实现期必盯项：

| ID | 风险 | 本 change 应对 |
|---|---|---|
| R1 | 外部依赖 str cell 的后处理 | Impact 标明 bugfix；发布说明可删 `_post_process_workbook` 数字修复 |
| R2 | 物化全量 rows 的峰值 | 与 sheetbook 同模型；用去掉急切 CSV 副本对冲 |
| R3 | `book_sheet_rows(xlsx_file)` 可见性漂移 | 同契约实现 + 可见性单测 |
| R4 | xlsx+csv 双消费缺 CSV | **范围外**；futures 预案，不在本 PR 假装已支持 |
| R5 | CSV resolve 误用于 ROWS-only | write 全改 tabular；缺 csv map 时 csv resolve 清晰失败 |
| R6 | Decimal/None/bool 边界 | 管道保真；MVP 覆盖；文件 round-trip 不承诺 |
| R7 | 只改 kind 不改 `format=excel` | tasks 强制整段进入 ROWS+excel 分支 |

**结论**: 无阻断项；R4 为已知缺口，用 futures 承接而非半吊子自动派生。

## 文档 / 生成边界

- 本变更 SSOT：本目录 `proposal.md` / `design.md` / `tasks.md` / `specs/**`。
- 延后/预案 SSOT：`llmanspec/futures/xlsx-file-numeric-type-loss/future.md`（勿在 change 目录再放 `future.md`）。
- 无 `.gen.` 手改；若文档站需提及行为，归档后走 `just gen-docs`（若有注入点）。
- MVP 示例保留在 `examples/numeric-type-loss/`（非生成物）。
