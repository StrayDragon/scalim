# StreamingColumnExcelSink：框架路径边界与建议

> 给 agent / 维护者的排错与选型指南。  
> 人类文档（策略何时启用）: `docs/doc/getting-started/excel-column-residency.md`  
> 证据: `llmanspec/changes/archive/2026-07-12-c0-streaming-column-excel-sink/`、`.../c0-streaming-column-excel-multi-batch/`、`.../c0-excel-column-residency-opt-in/`。

## 先分清三条路径

| 路径 | 实际 sink | 峰值 | 与 WINDOW |
|---|---|---|---|
| **YAML / workflow books** | 行 `ExcelSink` / workbook sheet | 行流式 | **无效**；`WINDOW`+composition → **fail-fast** |
| **IR 列式 `HOLD`（默认）** | `ColumnExcelSink` | 列缓存到 `close` | 默认，勿改除非有证据 |
| **IR 列式 `WINDOW`（opt-in）** | `StreamingColumnExcelSink` | 行窗刷盘；宽表可大幅降峰 | `ExcelColumnResidency.WINDOW` |

工厂: `src/scalim/execution/run_ir.py` → `_create_file_sink`。  
Enum: `scalim.execution.ExcelColumnResidency` / `scalim.dsl.yaml_dsl.ExcelColumnResidency`。

**入口矩阵（有手动、无自动）**：人类文档 `docs/doc/getting-started/excel-column-residency.md` §3；  
`DemandRunRuntimeOptions.excel_column_residency` 对 YAML books/`output_composition` **无效且会 fail-fast**；workflow 经 `WorkflowRunOptions.demand.runtime` 嵌套同一字段。

## 何时启用哪种策略（给用户的建议）

### 用 `HOLD`（默认）当

- 列/行规模不大，或峰值可接受
- 需要与历史 `ColumnExcelSink` 行为一致
- 不确定时：**保持默认**

### 用 `WINDOW` 当（须同时满足）

1. `OutputSpec.format=excel` 且 `streaming=False`（列式 IR 文件 sink）
2. 宽表/高行导致 `pre_close`/peak 不可接受（经验：百列 × 数万行起更明显）
3. **无** `output_composition`（非 YAML books 组合）

```python
from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, ExcelColumnResidency

DemandRunRuntimeOptions(excel_column_residency=ExcelColumnResidency.WINDOW)
```

### 与 0.10 row-wise fusion

列 sink 路径(含 `HOLD`/`WINDOW`)在 fusion 安全外壳内 **不融合**。宽表峰值用 WINDOW 砍 RSS 与 fusion 墙钟收益是正交问题;不要混谈。总览:`references/0.10-release-highlights.md`。

### 不要建议 `WINDOW` 当

- 用户走 YAML `resources.books`（已是行写出；假开关会 fail-fast）
- 用户想在 YAML 写 streaming knobs（**禁止**）
- 痛点是 shared-book 物化峰值（转介 futures spill，不是本 Enum）
- 调用方一次 `set_row_ids(全量)` 再按列写（应改为按 batch 追加）

### 手写 `StreamingColumnExcelSink` 当

- 完全自管写出 / 自定义 batch 窗
- 或不走 `_create_file_sink` 工厂

## Agent 硬边界

1. **MUST NOT** 发明 YAML `write.streaming` / residency 字段
2. YAML Excel 峰值 ≠ 缺 WINDOW；先说明行 sink 路径
3. 推荐 WINDOW 前确认是列式 IR（`streaming=False`）
4. shared-book **不能**插 StreamingColumn

## 证据口径

| shape | hold peak | multibatch WINDOW peak |
|---|---:|---:|
| 100k×300 | ~3.59GB | **~0.12GB**（~97%） |
