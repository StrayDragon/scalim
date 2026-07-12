# Proposal: column-excel-sink-write-memory

## Why

宽表 Excel 输出路径上，`ColumnExcelSink` 在 `close()` 前全量驻留列 dict，并在 close 时再经 openpyxl 物化。证据：

| 证据 | 路径 | 结论摘要 |
|---|---|---|
| 宽表爬坡 | `.tmp/evidence-mvp/column-excel-wide-climb/` | 300k×300 peak **26.45GB** / close ~602s；线性外推 1M×300≈~88GB |
| memray 20k×300 | `.../memray-20k300/` | `close` ≈84% 分配；openpyxl `append` ≈62% |
| **write_only A/B** | `.tmp/evidence-mvp/column-excel-write-only-ab/20260712T084537Z/` | 50k×300 fresh-process：peak **5.52→1.23GB**（−4.29GB）；close **103→77s**（−26s） |

`ExcelSink` 早已使用 `Workbook(write_only=True)`；`ColumnExcelSink` 此前用常规 `Workbook()`，导致 close 阶段单元格树与列缓存双峰。

## What Changes

1. **已落地（本 change apply）**：`ColumnExcelSink.close()` 改为 `Workbook(write_only=True)` + `create_sheet`，异常路径复用既有 `_best_effort_close_write_only_workbook_worksheets`；去掉多余 `list(row_values)` 拷贝
2. **测试**：回归夹具与 write_only 对齐
3. **仍不在范围**：YAML streaming knobs、行就绪刷盘、shared-book spill（见 design 后续项）

## Capabilities

### Modified Capabilities

- `output-sink-contracts` — ColumnExcelSink close 使用 write_only Workbook（与 ExcelSink 一致的内存写出策略）

## Impact

- **代码**: `src/scalim/sinks/_internal/excel.py`、`tests/sinks/test_sinks_excel_regressions.py`
- **破坏性**: 无 API 变更；输出内容应与原先一致（write_only 仅改变 openpyxl 内部物化方式）
- **证据 SSOT**: `.tmp/evidence-mvp/**`（不提交）

## 固定证据脚本

见本 change 内 `evidence-mvp/`（输出落 `.tmp/evidence-mvp/`，不提交）：

- `evidence-mvp/repro_write_only_ab.py`
- `evidence-mvp/repro_peak_measure.py`
- `evidence-mvp/README.md`

## 进度

- [x] 宽表爬坡 + memray
- [x] write_only A/B
- [x] 实现 ColumnExcelSink write_only close
- [x] design 更新
- [x] delta specs + tasks + validate
- [ ] qa / archive（用户确认后）
