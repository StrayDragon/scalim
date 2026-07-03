# MVP: 重复展示列名导出回归 demo

> 脱敏、独立可运行的参考例子。不含任何真实业务数据。

## 场景

用户希望导出给数据同事的**展示列名**可以重复(例如多个指标块共用「人数」「金额」),而底层输出字段 `field_id` 全局唯一。workflow 模式导出 `xlsx`/`csv` 时,曾出现后续同名列被首列值填充的数据错位 bug。

本 demo 覆盖三条写入路径,验证修复后数据按 `field_id` 正确对齐:

| 路径 | book kind | 中间工件 | 修复前 | 修复后 |
|:---|:---|:---|:---|:---|
| `xlsx_file` (workbook) | `xlsx_file` | `InMemoryCsv` | ❌ 数据错位 | ✅ 正确 |
| `xlsx_memory` (sheetbook) | `xlsx_memory` | `InMemoryRows` | ✅ 本就正确 | ✅ 正确 |
| `csv` (file) | — | `InMemoryCsv` | ❌ 数据错位 | ✅ 正确 |

## 数据(脱敏占位)

四个 `field_id` 唯一,展示名两两重复:

| field_id | 展示名(name) | 示例值 |
|:---|:---|:---|
| `pay_count_first` | 人数 | 7 |
| `pay_amount_first` | 金额 | 13111.26 |
| `pay_count_repeat` | 人数 | 1 |
| `pay_amount_repeat` | 金额 | 10510.00 |

每列值各不相同,便于一眼识别第 3/4 列是否被首列值(7 / 13111.26)填充。

## 运行

```bash
cd <repo-root>
uv run python llmanspec/changes/c10-fix-duplicate-display-headers/examples/duplicate-display-headers/run.py
```

## 期望输出(修复后)

```
xlsx_file header: ['人数', '金额', '人数', '金额']
xlsx_file data  : ['7', '13111.26', '1', '10510.0']
xlsx_memory header: ['人数', '金额', '人数', '金额']
xlsx_memory data  : [7, 13111.26, 1, 10510]
csv header: ['人数', '金额', '人数', '金额']
csv data  : ['7', '13111.26', '1', '10510.0']

全部通过: 重复展示列名下三路径数据均按 field_id 正确对齐,未被首列值填充。
```

> 注: `xlsx_file`(workbook)与 `csv` 路径经 `InMemoryCsv` 文本传输,值为字符串;
> `xlsx_memory`(sheetbook)路径保留原始数值类型。两者数值等价,本 demo 按数值归一化比较。

## bug 复现(修复前)

`xlsx_file` / `csv` 数据为 `[7, 13111.26, 7, 13111.26]`(第 3/4 列被首列值填充);
`xlsx_memory` 数据正确(本就不受影响)。

## 文件说明

| 文件 | 作用 |
|:---|:---|
| `demand.yaml` | demand 声明:重复展示名字段 + `header_fields_output_by: name` + 三路径输出绑定 |
| `workflow.yaml` | workflow 声明:`xlsx_file` + `xlsx_memory` 两个 book 资源 |
| `data_loader.py` | 内存 loader:返回脱敏占位数据 |
| `run.py` | 独立运行入口:执行 workflow + 验证三路径输出数据不错位 |

## 根因与修复

**根因**: workflow 的 `xlsx_file`/`csv` 路径,中间工件 `InMemoryCsv` 的 `header` 携带展示名(可重复),写入节点 `_build_alignment_mapping` 按列名 `Dict` 去重 → 重复名坍缩到首现 → 错位。

**源头修复**: 对齐永远基于唯一 `field_id`,展示名只用于表头行。把 `xlsx_memory`/sheetbook 已正确的设计(`InMemoryRows.header=field_id` + 独立 `export_header`)推广到 `xlsx_file`/workbook 与 `csv`/file,三路径统一。

详见 `llmanspec/changes/c10-fix-duplicate-display-headers/design.md`。
