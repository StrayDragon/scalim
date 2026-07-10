# notplan: c0-add-field-value-datetime（暂缓观察）

> **状态**: 已从 `llmanspec/changes/` 移入 `notplan/`，**不**作为当前可 apply 变更。  
> **原因**: 扩展 `FieldValue` 含 `datetime`/`date` 后，Excel/`openpyxl` 对 aware `datetime` 必须去 `tzinfo`；静默丢时区可能扭曲绝对时刻语义，需单独探索。  
> **当前运行时策略（临时）**: `InMemoryRowsSink` 对非 `FieldValue` 做 `str(value)`（方案 B），对齐旧 CSV 中间层，先解锁 pay-order 等业务。

## Why（仍成立）

`xlsx_file` → `InMemoryRows` 后，loader 的 `datetime`/`date` 会撞上 `FieldValue` 闭集。  
正式扩展值域是正确方向，但 Excel 边界与 tz 语义未收敛前不宜落地。

## openpyxl 实验结论（仓库 venv 3.1.5）

- naive `datetime` / `date`：可写可读
- aware `datetime`/`time`：`TypeError: Excel does not support timezones...`
- 因此若 A 落地，Excel 边界几乎必然要去 tz 或拒绝 aware——需产品决策后再转正

## 转正前必须回答

1. aware `datetime`：拒绝 / 去 tz 写出 / 转 UTC 再去 tz？
2. Excel 单元格要原生日期，还是文本日期可接受（B 已是文本）？
3. `time` 是否纳入 `FieldValue`？

## 转正路径

1. `llman-sdd-propose` 新建 active change（可复用本目录草案）
2. 收敛 design 中 tz 策略后 `llman-sdd-apply`
3. 落地后可移除 `InMemoryRowsSink` 的 `str()` 兼容分支（若值域已覆盖业务类型）

原 proposal/design/tasks/specs 仍保留在本目录供后续探索。
