# Design: c0-add-field-value-datetime

## Decision

扩展 `FieldValue` 闭集为 openpyxl 原生可绑定的时间类型全集：

```text
FieldValue = int | float | Decimal | str | bool | None
           | datetime | date | time | timedelta
```

约束：

- **中间态原样保存**（含 aware `datetime`/`time`）；框架 MUST NOT `str()`、MUST NOT `replace(tzinfo=None)`、MUST NOT 转 UTC。
- Excel / workbook / sheetbook 写出边界：非 `str` **透传**给 openpyxl；aware 由 openpyxl 抛错（与用户直接用库一致）。
- `date` 写出后 openpyxl 读回可能是午夜 `datetime`（文档化；不强制 Python 类型 round-trip 恒等）。
- 未知类型：`InMemoryRowsSink` / 相关校验 **TypeError fail-fast**（撤回 `0ebee6d6` 的 `str()` 补丁）。

## Why not strip tz at Excel boundary

旧 notplan 曾计划 `prepare_excel_cell_value` 去 tz。已否决：

- 会静默改写用户数据（墙钟 vs 绝对时刻语义不清）。
- 与「直接 openpyxl 会报错」的根源不一致，框架反而更别扭。
- 产品接受小 breaking：aware 由业务侧处理。

## Why include time / timedelta

openpyxl `TIME_TYPES` 含四者；探测 Layer A/B 均 `data_type=d` 可写。  
只扩 `datetime`/`date` 会留下新的半吊子值域（`time`/`timedelta` 再走 `str()`）。本 change 一次对齐。

## CSV conversion

`in_memory_rows_to_in_memory_csv`：`None -> ""`，其余 `str(value)`（含时间类型默认 `str`）。不引入专用格式化配置。

## Runtime touchpoints

| 位置 | 动作 |
|---|---|
| `typedefs.py` | 扩展 `FieldValue` |
| `sinks/_internal/rows.py` | `_FIELD_VALUE_TYPES`；移除 `str()` 回退 |
| `conversion_sources.py` / `runtime_linking.py` / `output_composition_yaml.py` | `_SUPPORTED_FIELD_VALUE_TYPES` 同步 |
| Excel / workbook / sheetbook | 确认透传；**不**新增去 tz helper |
| specs | 修改 r88 / r393；新增 Excel 透传契约 |

## Before / after（报告行为）

| 输入 | 现在（str 补丁） | 本 change 后 |
|---|---|---|
| naive `datetime` | Excel 文本 | Excel 日期 (`d`) |
| aware `datetime` | 文本成功 | openpyxl `TypeError` |
| 未知类型 e.g. custom | `str()` | `TypeError` |
| int/Decimal/bool | typed | 不变 |

## Future（非本 change）

其它 sink（`pandas`、parquet、未来列式存储）的类型兼容矩阵：

- `FieldValue` 是 **tabular intermediate SSOT**，不是「每个 sink 的超集」。
- 新 sink 落地时须单独定义：哪些 `FieldValue` 成员可原样写出、哪些需显式转换、哪些 fail-fast。
- **禁止**为迁就某 sink 而在 ROWS 中间态静默改写类型（重复本次教训）。
- 候选 follow-up：`field-value-sink-compatibility-matrix`（pandas / parquet 等）。

## Trade-offs

| 选项 | 结论 |
|---|---|
| Excel 去 tz | **否决** |
| 中间态拒绝 aware | **否决**（与「不改数据」冲突；错误应出在写出边界） |
| 保留 str() 补丁 | **否决** |
| 本轮加 value_cast | **延后** |
| 含 time/timedelta | **采用** |

## Test plan

- unit：`InMemoryRowsSink` 接受四类时间类型；未知类型 TypeError；不再 `str()` datetime
- unit/sink：`ExcelSink` naive → `data_type=d`；aware → 与 openpyxl 同类 TypeError
- e2e：最小 1-run workflow（对齐 `.tmp/repro/openpyxl-write-type-support/probe_write_types.py` Layer D）
- regression：既有 numeric/bool/None/str 路径不变
