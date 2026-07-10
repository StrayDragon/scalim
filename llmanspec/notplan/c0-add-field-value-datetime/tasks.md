# tasks: c0-add-field-value-datetime

## 1. 扩展 FieldValue SSOT

- [ ] 1.1 `src/scalim/typedefs.py`：`FieldValue` 增加 `datetime`、`date`（import stdlib）
- [ ] 1.2 文档字符串写明：仅 naive `datetime`；aware 非法

## 2. InMemoryRows 校验

- [ ] 2.1 `sinks/_internal/rows.py`：`_FIELD_VALUE_TYPES` / `_is_field_value` 接受 `datetime`/`date`
- [ ] 2.2 aware `datetime` fail-fast（明确 TypeError 文案）
- [ ] 2.3 更新 `tests/sinks/test_sink_rows.py`

## 3. Excel / workbook 边界

- [ ] 3.1 确认 `escape_excel_formula` 不改写非 str（已有）
- [ ] 3.2 单测：typed rows 含 naive datetime/date 写入 xlsx 可读回
- [ ] 3.3（可选）sheetbook 对称单测

## 4. Specs / 校验

- [x] 4.1 delta：`workflow-intermediate-store` 修改 r1 值域列举
- [x] 4.2 delta：`workflow-shared-output-containers` 修改 r23 值域列举
- [x] 4.3 delta：`output-sink-contracts` 增加 Excel 时间类型契约
- [ ] 4.4 `llman sdd validate c0-add-field-value-datetime --strict --no-interactive`
- [ ] 4.5 相关 pytest + `just qa`（或至少 sinks/workflow 子集）
