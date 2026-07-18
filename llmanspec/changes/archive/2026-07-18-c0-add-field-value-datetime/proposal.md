# Proposal: c0-add-field-value-datetime

> **状态**: 已从 `notplan/` **转正**为 active change（2026-07-18）。  
> **取代**: 旧 notplan 中「Excel 边界去 `tzinfo` / UTC」策略；临时 `InMemoryRowsSink.str()` 兼容补丁（`0ebee6d6`）。

## Why

c5 将 xlsx workflow 中间态切到 typed `InMemoryRows` 后，`FieldValue` 闭集不含时间类型。  
`0ebee6d6` 对非 `FieldValue` 做 `str()` 以救活业务，造成：

- 直写 `ExcelSink`：naive `datetime` → Excel 日期
- workflow / `InMemoryRows`：同一值 → **文本单元格**

探测证据：`.tmp/evidence/openpyxl-write-type-support/`（Layer A/B OK，C/D 变 `str`）。

产品决策（2026-07-18）：

1. **不隐式修改用户数据**（含中间态）：不去 tz / 不转 UTC / 不做 silent `str()`。
2. **与直接使用 openpyxl 同源**：aware 时间在写出边界由 openpyxl 报错即可。
3. **接受小 breaking**：依赖「日期被写成文本」或依赖 aware 静默成功的用户代码需自行调整。
4. **值域**：纳入 openpyxl `TIME_TYPES` 全部成员：`datetime` / `date` / `time` / `timedelta`。

## What Changes

1. `FieldValue` 扩展为包含 `datetime`、`date`、`time`、`timedelta`（naive/aware 均允许进入中间态）。
2. `InMemoryRows` / `InMemoryRowsSink` / 相关 `_SUPPORTED_FIELD_VALUE_TYPES` 同步接受上述类型；**移除** `str()` 兼容回退；未知类型恢复 **TypeError fail-fast**。
3. Excel / workbook / sheetbook 写出：**原样透传**非 `str` 值；`escape_excel_formula` 仍仅处理 `str`。**禁止** `prepare_excel_cell_value` 去 tz 或其它改写。
4. `in_memory_rows_to_in_memory_csv`：时间值仍走显式 `str(value)`（CSV 等价语义；不是静默改 ROWS）。
5. 更新列举 `FieldValue` 值域的 specs（r88 / r393 + output-sink 契约）。
6. 测试：unit + ExcelSink + 最小 1-run workflow（对齐 MVP probe）。

非目标（本 change）：

- YAML `value_cast: datetime|date|...`（另案）
- numpy/pandas 时间类型（loader 自行 `.to_pydatetime()`）
- pandas / parquet 等其它 sink 的类型矩阵（见 design Future）
- 修改 openpyxl 本身

## Capabilities

- `workflow-intermediate-store`（`FieldValue` / `InMemoryRows` 值域）
- `workflow-shared-output-containers`（typed xlsx pipeline 值域列举）
- `output-sink-contracts`（Excel 边界对时间类型：透传、不改写）

## Impact

- **Breaking（正向）**：
  - workflow xlsx 中 naive 时间从**文本**变为 **Excel 日期**（依赖文本后处理的代码需改）。
  - aware 时间：从「静默写成带 `+00:00` 的文本」变为 **openpyxl TypeError**（与手写一致；用户须在 loader 侧处理）。
  - 未知非 `FieldValue` 类型：从 `str()` 变为 **TypeError**。
- **Compat**：CSV 显式转换路径仍字符串化；int/float/Decimal/bool/None/str 不变。
- **Perf**：去掉中间 `str()`，与数字 typed 路径一致；无额外转换层。
- **Ethics**: `risk_level=medium`；禁止框架静默改写时间语义；禁止把 Excel 限制伪装成成功写出。

## Supersedes

- `llmanspec/notplan/c0-add-field-value-datetime/`（保留指针 stub）
- `llmanspec/futures/xlsx-file-numeric-type-loss/future.md` 中「FieldValue 纳入 datetime/date」later 项
