# notplan stub: c0-add-field-value-datetime

> **已转正** → `llmanspec/changes/archive/2026-07-18-c0-add-field-value-datetime/`（2026-07-28 冻结于 `freezed_changes.7z.archived`；实现 commit `d5aa943c`）  
> 本目录仅保留指针，**禁止**再按下方旧策略开第二份 change。

## 被本转正提案承接 / 替代的内容

| 旧 notplan 内容 | 状态 |
|---|---|
| 扩展 `FieldValue` 含时间类型 | **承接**（且扩到 `time`/`timedelta`） |
| 撤 `InMemoryRowsSink` 的 `str()` 补丁 | **承接** |
| Excel 边界 `prepare_excel_cell_value` **去 tz** | **替代 / 否决** — 改为原样透传，与 openpyxl 同源报错 |
| 中间态拒绝或改写 aware | **否决** — aware 可进 ROWS；错误出在写出边界 |
| YAML `value_cast: datetime` | **仍非本 change**（另案；勿在本 stub 重开） |

## 为何曾停在 notplan

`0ebee6d6` 用 `str()` 救活业务；正式扩类型卡在「是否去 tz」。  
2026-07-18 产品定案：**不去 tz、不改用户数据**，故转正并改写 design。

## 证据 / MVP

`.tmp/repro/openpyxl-write-type-support/probe_write_types.py`  
`.tmp/evidence/openpyxl-write-type-support/`

## 后续勿重复做

- 不要再新建 `add-field-value-datetime` / `strip-tz-at-excel-boundary` 类 change。
- pandas / parquet 等其它 sink 类型矩阵：见 active change `design.md` Future，另立 change。
