# Design: ColumnExcelSink write_only close（已取证并落地最小改动）

## 证据

### 爬坡（300 列，RSS 熔断 28GB）

| shape | peak RSS | close wall |
|---|---:|---:|
| 100k×300 | 9.01GB | ~200s |
| 200k×300 | 17.96GB | ~412s |
| 300k×300 | 26.45GB | ~602s |

### memray 20k×300

- `close` ≈84% Total Memory；`append` ≈62%

### A/B write_only（50k×300，fresh process）

| arm | peak RSS | close_s |
|---|---:|---:|
| baseline `Workbook()` | 5.52GB | 103.4s |
| `Workbook(write_only=True)` | **1.23GB** | **76.6s** |

决策：**立即落地 write_only**（与 `ExcelSink` 对齐）；ROI 明确且行为兼容。

## 实现要点

- `ColumnExcelSink.close`：`Workbook(write_only=True)` + `create_sheet(sheet_name)`
- 失败路径：`_best_effort_close_write_only_workbook_worksheets`
- 不再依赖 `wb.active`

## 后续（非本 PR 必做）

- 列缓存仍驻留到 close 结束 → 行就绪刷盘 / StreamingColumnExcelSink（notplan）另案
- 更大 shape（≥200k）复测 write_only 峰值曲线
