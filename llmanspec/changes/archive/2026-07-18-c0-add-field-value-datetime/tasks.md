# tasks: c0-add-field-value-datetime

## 1. 扩展 FieldValue SSOT

- [x] 1.1 `src/scalim/typedefs.py`：`FieldValue` 增加 `datetime` / `date` / `time` / `timedelta`
- [x] 1.2 文档字符串：中间态原样保存；aware 不在 FieldValue 层拒绝；Excel 由 openpyxl 决定成败

## 2. 运行时校验与撤补丁

- [x] 2.1 `sinks/_internal/rows.py`：更新 `_FIELD_VALUE_TYPES`；**移除** `str()` 兼容回退；未知类型 TypeError
- [x] 2.2 同步 `_SUPPORTED_FIELD_VALUE_TYPES`：`conversion_sources.py`、`runtime_linking.py`、`output_composition_yaml.py`（若有重复闭集）
- [x] 2.3 更新 `tests/sinks/test_sink_rows.py`（含 datetime 保留 + 未知类型 fail-fast）

## 3. Excel / workbook 边界

- [x] 3.1 确认无去 tz / 无 `prepare_excel_cell_value` 改写；`escape_excel_formula` 仅 `str`
- [x] 3.2 单测：naive `datetime`/`date`/`time`/`timedelta` 写入 xlsx 为日期类单元格
- [x] 3.3 单测：aware `datetime` 写出路径抛出与 openpyxl 一致的 TypeError（不静默 str）
- [x] 3.4（可选）sheetbook / workbook commit 对称冒烟（由 ExcelSink + workflow e2e 覆盖）

## 4. Workflow e2e

- [x] 4.1 最小 1-run workflow：loader 返回 naive 时间 → 读回非 `str`（对齐 probe Layer D）
- [x] 4.2 回归：numeric/bool/None/str 仍 typed

## 5. Specs / 校验 / 指针

- [x] 5.1 delta：`workflow-intermediate-store` 修改 r88 + 增补 r912
- [x] 5.2 delta：`workflow-shared-output-containers` 修改 r393
- [x] 5.3 delta：`output-sink-contracts` 增补 r918（Excel 透传、禁止去 tz）
- [x] 5.4 notplan stub + futures 指针已更新（避免重复做）
- [x] 5.5 `llman sdd validate c0-add-field-value-datetime --strict --no-interactive`
- [x] 5.6 相关 pytest；合并前 `just qa`（或至少 sinks/workflow 子集）
