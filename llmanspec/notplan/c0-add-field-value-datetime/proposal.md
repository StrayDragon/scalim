# Proposal: c0-add-field-value-datetime

> **notplan / 暂缓**: 本草案已移出 active changes。运行时先用 `InMemoryRowsSink` 对非 `FieldValue` 做 `str()`（方案 B）。转正前须收敛 aware `datetime` 的 Excel 策略（见同目录 `README.md`）。

## Why

`c5-xlsx-file-numeric-type-loss` 将 `xlsx_file` workflow-managed 中间态切到 `InMemoryRows` 后，
业务 loader 常见的 `datetime`/`date`（例如 pay-order 的 `create_datetime`）在
`InMemoryRowsSink` 处 fail-fast：`FieldValue` 闭集不含时间类型。

此前 `InMemoryCsvSink` 对任意值 `str(value)`，时间被静默字符串化，问题被掩盖。
扩展 `FieldValue` 是正确的类型 SSOT 修复；sink 边界 `str()` 仅为观察期兼容。

实验（openpyxl 3.1.5）：
- naive `datetime` / `date`：可写可读（`date` 读回为 `datetime` 午夜）
- timezone-aware `datetime`：openpyxl 拒绝；若去 `tzinfo` 可能扭曲绝对时刻语义（阻塞转正）
- `time`：可写（本 change **不**纳入 `FieldValue`，避免范围膨胀）

## What Changes

1. `FieldValue` 扩展为包含 `datetime` 与 `date`（不区分 naive/aware）。
2. `InMemoryRows` / `InMemoryRowsSink` 校验同步接受上述类型。
3. Excel / workbook / sheetbook 写出边界：`prepare_excel_cell_value` 对 aware `datetime` 去 `tzinfo` 后交给 openpyxl；`str` 仍走公式转义。
4. `in_memory_rows_to_in_memory_csv`：时间值仍走既有 `str(value)`（CSV 等价语义不变）。
5. 更新列举 `FieldValue` 值域的 specs。

非目标：
- 不把 `time` 纳入 `FieldValue`（可另案）
- 不改 YAML `value_cast` 枚举（本 change 不新增 `value_cast: datetime`）

## Capabilities

- `workflow-intermediate-store`（`FieldValue` / `InMemoryRows` 值域）
- `workflow-shared-output-containers`（r23 值域列举）
- `output-sink-contracts`（Excel 边界对时间类型的契约）

## Impact

- **Breaking（正向）**：原先依赖“xlsx_file 把 datetime 写成文本”的后处理可能看到真正的 Excel 日期单元格。
- **Compat**：CSV 路径与 `in_memory_rows_to_in_memory_csv` 仍字符串化；aware 在 Excel 边界丢 tzinfo。
- **Docs/SSOT**：specs 为 SSOT；无 `.gen.` 手改。
- **Ethics**: `risk_level=medium`；禁止在 FieldValue 层因 tz 拒绝合法业务时间；Excel 去 tz 为 openpyxl 兼容所必需。
