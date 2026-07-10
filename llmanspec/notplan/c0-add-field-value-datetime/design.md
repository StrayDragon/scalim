# Design: c0-add-field-value-datetime

## Decision

扩展 `FieldValue` 闭集：

```text
FieldValue = int | float | Decimal | str | bool | None | datetime | date
```

约束：
- **接受任意** `datetime`/`date`（不区分 naive/aware；不关心 `tzinfo`）。
- `date` 允许；openpyxl 写出后读回可能是 `datetime` 午夜（文档化，不强制 round-trip 类型恒等）。
- Excel/`openpyxl` 不支持 timezone：写出边界通过 `prepare_excel_cell_value` 对 aware `datetime` 去掉 `tzinfo`（保留墙钟时间分量）。

## Why not str() at sink

c5 的目标是 typed SSOT。对时间再 `str()` 会把 Excel 日期列变回文本，部分抵消 ROWS 收益，且与 openpyxl 原生日期能力冲突。

## CSV conversion

`in_memory_rows_to_in_memory_csv` 保持 `None -> ""`，其余 `str(value)`（含 `datetime`/`date` 的默认 `str` 形态）。不引入专用格式化配置（非本 change）。

## Excel boundary

`prepare_excel_cell_value`：
1. aware `datetime` → `replace(tzinfo=None)`
2. 再走 `escape_excel_formula`（仅 `str`）

## Trade-offs

| 选项 | 取舍 |
|---|---|
| 含 `time` | 延后；业务未阻塞且 Excel 语义更窄 |
| aware 在 FieldValue 层拒绝 | **否决**；业务不关心 tz，放宽接受 |
| Excel 边界去 tz | **采用**；对齐 openpyxl 限制 |
| 仅文档要求业务 cast | 拒绝为框架答案；ROWS 路径应一等支持时间 |

## Test plan (implementation)

- unit：`InMemoryRowsSink` 接受 naive/aware datetime 与 date；拒绝未知类型
- unit：workbook/sheetbook / prepare_excel_cell_value 对 aware 去 tz 后可写出
- regression：既有 int/float/Decimal/bool/None/str 路径不变
